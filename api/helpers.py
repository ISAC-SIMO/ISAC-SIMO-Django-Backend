import base64
import json
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
import uuid
from importlib import reload
from zipfile import ZipFile

import filetype
import mistune
import requests
from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile
from PIL import Image
import numpy as np
import tensorflow as tf
from keras import backend as K
# import keras

import isac_simo.classifier_list as classifier_list
import cv2
import pathlib
import numpy as np
import random
from api.models import Classifier, ImageFile
from django.contrib import messages
from projects.models import Projects
from django.http import HttpResponse
from django.shortcuts import redirect
from operator import itemgetter
import io
import sys

from ibm_watson import VisualRecognitionV3, ApiException, VisualRecognitionV4
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_watson.visual_recognition_v4 import AnalyzeEnums, FileWithMetadata

PIPELINE_CONTINUE_ON = ("go","gos","nogo","nogos")
def shouldContinue(res): 
    # IN CASE OF 
    # 1. DETECT MODEL action as Classifier it will always continue if next pipeline exists
    # 2. PreProcessor also always continues because there is no go/nogo it just processes images
    if str(res).strip().replace(" ","").lower() in PIPELINE_CONTINUE_ON:
        return True
    return False

def reload_classifier_list():
    try:
        reload(classifier_list)
    except Exception as e:
        print('--------- [ERROR] FAILED TO RELOAD CLASSIFIER LIST MODULE [ERROR:OOPS] --------')

def transform_image(img, ext, saveto, rotate, warp, inverse):
    all_unzipped_images_list = []
    # 0 = horizontal
    # 1 = vertical
    # -1 = both way aka inverse or mirror
    print('TRANSFORMING IMAGES---')
    for i in [0,1,-1]:
        t_image = cv2.flip( img, i )
        filename = '{}{}'.format(uuid.uuid4().hex, ext)
        cv2.imwrite(saveto + filename, t_image) # save frame as IMAGE file
        all_unzipped_images_list.append(saveto + filename) # add image to array (transformed)
    
    if rotate:
        print('ROTATING IMAGES---')
        for i in [30,60,-60,120]: # Rotate in these angles
            (h, w) = img.shape[:2]
            center = (w / 2, h / 2)
            # Perform the rotation
            M = cv2.getRotationMatrix2D(center, i, 1.0)
            rotated = cv2.warpAffine(img, M, (w, h), borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0)) # borderMode=cv2.BORDER_TRANSPARENT
            filename = '{}{}'.format(uuid.uuid4().hex, ext)
            cv2.imwrite(saveto + filename, rotated) # save frame as IMAGE file
            all_unzipped_images_list.append(saveto + filename) # add image to array (rotated)

    if warp:
        print('WARPING IMAGES---')
        h, w = img.shape[:2]
        rows, cols = img.shape[:2]
        src_points = np.float32([[0,0], [w-1,0], [0,h-1], [w-1,h-1]])
        des_points = np.float32([[0,0], [w-1,0], [0,h-1], [w-1,h-1]])
        for j in ['t','l','r','b']:
            if j == 't':
                des_points = np.float32([[1,0], [w-1,0], [int(0.2*w),h-1], [w-int(0.2*w),h-1]])
            elif j == 'l':
                des_points = np.float32([[0,0], [w-10,int(0.2*h)], [0,h], [w-10,h-int(0.2*h)]])
            elif j == 'r':
                des_points = np.float32([[10,int(0.20*h)], [w,0], [10,h-int(0.20*w)], [w,h]])
            elif j == 'b':
                des_points = np.float32([[int(0.2*w),10], [w-int(0.2*w),10], [0,h], [w,h]])

            if j:
                M = cv2.getPerspectiveTransform(src_points, des_points)
                out = cv2.warpPerspective(img, M, (w,h),flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=(0,0,0))
                filename = '{}{}'.format(uuid.uuid4().hex, ext)
                cv2.imwrite(saveto + filename, out) # save frame as IMAGE file
                all_unzipped_images_list.append(saveto + filename) # add image to array (rotated)

    if inverse:
        print('INVERTING IMAGES---')
        inverted = ~img # simple invert matrix (uninary)
        filename = '{}{}'.format(uuid.uuid4().hex, ext)
        cv2.imwrite(saveto + filename, inverted) # save frame as IMAGE file
        all_unzipped_images_list.append(saveto + filename) # add image to array (rotated)

        print('CANNY EDGE DETECT IN IMAGES---')
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) # convert to gray-ish
        canvas = cv2.Canny(gray, 30, 100) # threshold can be changes (lower gives more detail but also noise)
        filename = '{}{}'.format(uuid.uuid4().hex, ext)
        cv2.imwrite(saveto + filename, canvas) # save frame as IMAGE file
        all_unzipped_images_list.append(saveto + filename) # add image to array (rotated)

    return all_unzipped_images_list

##################################################
##################################################
# Offline Model test with file and offline model (not classifier)
# README.md might be helpful
def test_offline_image(image_file, offline_model):
    if not image_file or not offline_model:
        return False

    img = Image.open(image_file).resize((150, 150))
    x = np.array(img)/255.0

    saved_model = None
    if not os.path.exists(os.path.join('media/offline_models/')):
        saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+offline_model.filename()
    else:
        saved_model = os.path.join('media/offline_models/', offline_model.filename())
    
    try:
        offlineModelLabels = json.loads(offline_model.offline_model_labels)
    except Exception as e:
        print(e)
        offlineModelLabels = []

    # Check type of model
    # h5, hdf5, keras, py
    result = [[]]
    if offline_model.model_format in ('h5', 'hdf5', 'keras'): # tf.keras models
        try:
            new_model = tf.keras.models.load_model(saved_model)
            result = new_model.predict(x[np.newaxis, ...])
            if type(result) != list:
                result = result.tolist()
        except Exception as e:
            img.close()
            print('Failed to run h5,hdf5,kears Offline Model')
            print('POSSIBLE VALUE ERROR WITH INVALID SEQUENCE OF IMAGE ARRAY')
            print(e)
            return False
    elif offline_model.model_format in ('py'): # python script
        # Trying to run saved offline .py model (loading saved py file using string name)
        try:
            print('----running saved offline model .py------')
            print(str(saved_model))
            import importlib
            loader = importlib.machinery.SourceFileLoader('model', saved_model)
            handle = loader.load_module('model')
            result = handle.run(img, offlineModelLabels) # Saved Model .py must have run function (see readme.md in /api)
            if type(result) is not list or len(result) <= 0:
                result = [[]]
                print('py local model -- BAD response (not list)')
        except Exception as e:
            print(e)
            print('Failed to run .py Offline Model')
    else:
        print('This Offline Model Format is not supported')

    data = []
    
    i = 0
    for r in result[0]:
        if len(offlineModelLabels) > i:
            label = offlineModelLabels[i]
        else:
            label = 'No.'+str(i+1)

        data.append({
            "class": label,
            "score": r,
            "location": result[1][i] if (len(result) > 1 and len(result[1]) > i and type(result[1][i]) == dict) else None
        })
        i += 1

    result_type = ''
    score = '0'
    if len(result[0]) > 0:
        try:
            result_type = offlineModelLabels[result[0].index(max(result[0]))].lower()
        except:
            result_type = 'no.'+str(result[0].index(max(result[0])) + 1)
        finally:
            score = max(result[0])
    
    tf.keras.backend.clear_session()
    # tf.reset_default_graph()
    img.close()
    return {'data':data, 'score':score, 'result':result_type}

###################
## Detect Object ##
###################
def detect_image(image_file, detect_model, offline=False, no_temp=False, ibm_api_key=False, ibm_service_url=None, save_to_path=None):
    MIN_SCORE_REQUIRED = 0.1

    # IF Save To Path is sent in parameter. Use that instead. Could be pre-processed image you know.
    if save_to_path:
        file_url = save_to_path
    else:
        # Find Image Path (used to open)
        file_url = str(os.path.abspath(os.path.dirname(__name__))) + image_file.file.url
        if not os.path.exists(file_url):
            file_url = os.environ.get('PROJECT_FOLDER','') + image_file.file.url
        print('Detecting Image Object...')
        saveto = None

    # IF Is offline Model and detect model is given (detect_model = offline_model object)
    if offline and detect_model and os.path.exists(file_url):
        print('Detecting Image Object [Offline Model]...')
        res = test_offline_image(file_url, detect_model)
        if res:
            if not no_temp:
                image_file.object_type = res.get('result','')
            pipeline_status = {}
            try:
                pipeline_status = json.loads(image_file.pipeline_status)
            except Exception as e:
                pipeline_status = {}
            # Add Pipeline detected detail (Note: old pipeline replaced if new detect model is called upon it)
            pipeline_status['All Detected'] = pipeline_status.get('All Detected',[]) + res.get('data', [])
            pipeline_status[detect_model.name] = {
                'score': res.get('score'),
                'result': res.get('result')
            }
            image_file.pipeline_status = json.dumps(pipeline_status)
            image_file.save()
            print(res.get('result','-Nothing Detected-'))

            # MULTIPLE OBJECT_TYPE ARE DETECTED THEN ALL ARE CROPPED AND SAVED AS IMAGE_FILE
            # Loop through all data[{class:'',score:''}]
            allDetected = []
            if res.get('data', False) and len(res.get('data')) > 0: # If res.data exists
                resdata = sorted(res.get('data'), key=itemgetter('score'), reverse=True)

                i = 0
                for data in resdata:
                    try:
                        if data.get('class', False) and data.get('score', False) and float(data.get('score')) >= MIN_SCORE_REQUIRED:
                            # Open the file_url image
                            img = Image.open(file_url)
                            img = img.convert('RGB')
                            w, h = img.size
                            if data.get('location', False):
                                img = img.crop(( data.get('location').get('left', 0), data.get('location').get('top', 0), data.get('location').get('left', 0)+data.get('location').get('width', w), data.get('location').get('top', 0)+data.get('location').get('height', h) ))
                                # Crop if required
                            # Save to temporary for temp use
                            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
                            if not os.path.exists(os.path.join('media/temp/')):
                                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                            else:
                                saveto = os.path.join('media/temp/', filename)
                            
                            img.save(saveto, format='JPEG', quality=90)

                            # Only for 1st detect (update original image_file & for other new other_image_file is created)
                            if i == 0:
                                allDetected.append({ # add 0th item to default image_file
                                    "object_type": data.get('class'),
                                    'image_file': image_file,
                                    'temp_image': saveto,
                                })
                                i += 1
                                continue

                            i += 1

                            # In Memory image used to create ImageFile Model for new detect model result
                            output = io.BytesIO()
                            img.save(output, format='JPEG', quality=90)
                            output.seek(0)
                            memImage = InMemoryUploadedFile(output, 'ImageField', 'temp.jpg', 'image/jpeg', sys.getsizeof(output), None)
                            pipeline_status = {}
                            pipeline_status[detect_model.name] = {
                                'score': data.get('score'),
                                'result': data.get('class')
                            }
                            other_image_file = ImageFile.objects.create(image=image_file.image, file=memImage, object_type=data.get('class'), pipeline_status=json.dumps(pipeline_status))

                            img.close()

                            allDetected.append({
                                "object_type": data.get('class'),
                                'image_file': other_image_file,
                                'temp_image': saveto,
                            })
                    except Exception as e:
                        print(e)
                        print('--failing appending to allDetected other index of detection--')
                        continue
            
            # Loop End for all score
            print(allDetected)

            return allDetected
            
        else:
            return False
    else:
        # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
        if os.path.exists(file_url) and (ibm_api_key or settings.IBM_API_KEY) and (classifier_list.detect_object_model_id or detect_model) and ibm_service_url:
            object_id = classifier_list.detect_object_model_id
            if detect_model:
                object_id = detect_model

            # Authenticate the IBM Watson API
            api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
            # post_data = {'collection_ids': object_id, 'features':'objects', 'threshold':'0.15'} # 'threshold': '0.15 -1'
            # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
            # print(auth_base)

            # post_header = {'Accept':'application/json','Authorization':auth_base}
            
            # Temporary Resized Image (basewidth x calcheight)(save_to_path from param comes if looped through)
            basewidth = 300
            temp = Image.open(file_url)
            wpercent = (basewidth/float(temp.size[0]))
            hsize = int((float(temp.size[1])*float(wpercent)))
            # temp = temp.resize((basewidth,hsize), Image.ANTIALIAS)
            ext = image_file.file.url.split('.')[-1]
            filename = '{}.{}'.format(uuid.uuid4().hex, ext)

            if not os.path.exists(os.path.join('media/temp/')):
                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
            else:
                saveto = os.path.join('media/temp/', filename)

            print(saveto)
            
            temp.save(saveto)
            resized_image_open = open(saveto, 'rb')
            
            # post_files = {
            #     'images_file': resized_image_open,
            # }

            # UPDATED WATSON API
            authenticator = IAMAuthenticator(api_token)
            visual_recognition = VisualRecognitionV4(
                version='2019-02-11',
                authenticator=authenticator
            )

            visual_recognition.set_service_url(ibm_service_url)

            try:
                response = visual_recognition.analyze(
                    collection_ids=[object_id],
                    features=[AnalyzeEnums.Features.OBJECTS.value],
                    images_file=[
                        FileWithMetadata(resized_image_open)
                    ])
                content = response.get_result()
                status = response.get_status_code()
            except ApiException as ex:
                print('IBM Response was BAD (During Detect) - (e.g. image too large)')
                print(ex.message)
                return False

            # DEPRECATED API
            # # Call the API
            # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v4/analyze?version=2019-02-11', files=post_files, headers=post_header, data=post_data)
            # status = response.status_code
            # try:
            #     content = response.json()
            # except ValueError:
            #     # IBM Response is BAD
            #     print('IBM Response was BAD (During Detect) - (e.g. image too large)')
            #     return False
            
            print(status)
            print(content)
            # If success save the data
            if(status == 200 or status == '200' or status == 201 or status == '201'):
                if "collections" in content['images'][0]['objects']:
                    if(content['images'][0]['objects']['collections'][0]['objects']):
                        sorted_by_score = sorted(content['images'][0]['objects']['collections'][0]['objects'], key=lambda k: k['score'], reverse=True)
                        print(sorted_by_score)
                        if(sorted_by_score and sorted_by_score[0]): # Set Score`
                            if not no_temp:
                                image_file.object_type = sorted_by_score[0]['object']
                            pipeline_status = {}
                            try:
                                pipeline_status = json.loads(image_file.pipeline_status)
                            except Exception as e:
                                pipeline_status = {}
                            # Add Pipeline detected detail (Note: old pipeline replaced if new detect model is called upon it)
                            label = object_id
                            pipeline_status['All Detected'] = pipeline_status.get('All Detected',[]) + sorted_by_score
                            pipeline_status[label] = {
                                'score': sorted_by_score[0]['score'],
                                'result': sorted_by_score[0]['object']
                            }
                            image_file.pipeline_status = json.dumps(pipeline_status)
                            image_file.save()
                            resized_image_open.close()

                            # MULTIPLE OBJECT_TYPE ARE DETECTED THEN ALL ARE CROPPED AND SAVED AS IMAGE_FILE
                            # Loop through all ...[objects]
                            allDetected = []
                            resized_image_open.close()
                            os.remove(saveto)
                            i = 0

                            for data in sorted_by_score: # from 1 (0 already added with default image_file above)
                                try:
                                    if data.get('object', False) and data.get('score', False) and float(data.get('score')) >= MIN_SCORE_REQUIRED:
                                        if not no_temp: # Used in object_detect acting as a classifier 
                                            img = Image.open(file_url)
                                            img = img.convert('RGB')
                                            w, h = img.size
                                            if data.get('location', False):
                                                img = img.crop(( data.get('location').get('left', 0), data.get('location').get('top', 0), data.get('location').get('left', 0)+data.get('location').get('width', w), data.get('location').get('top', 0)+data.get('location').get('height', h) ))
                                            
                                            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
                                            if not os.path.exists(os.path.join('media/temp/')):
                                                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                                            else:
                                                saveto = os.path.join('media/temp/', filename)
                                            
                                            img.save(saveto, format='JPEG', quality=90)

                                        # Only for 1st detect (update original image_file & for other new other_image_file is created)
                                        if i == 0:
                                            allDetected.append({ # add 0th item to default image_file
                                                'object_type': sorted_by_score[0]['object'].lower(),
                                                'score': sorted_by_score[0]['score'],
                                                'image_file': image_file,
                                                'temp_image': saveto,
                                            })
                                            i += 1
                                            continue

                                        i += 1

                                        # In Memory image used to create ImageFile Model for new detect model result
                                        if not no_temp: # Used in object_detect acting as a classifier 
                                            output = io.BytesIO()
                                            img.save(output, format='JPEG', quality=90)
                                            output.seek(0)
                                            memImage = InMemoryUploadedFile(output, 'ImageField', 'temp.jpg', 'image/jpeg', sys.getsizeof(output), None)
                                            pipeline_status = {}
                                            pipeline_status['Detect Model: '] = {
                                                'score': data.get('score'),
                                                'result': data.get('object')
                                            }
                                            other_image_file = ImageFile.objects.create(image=image_file.image, file=memImage, object_type=data.get('object'), pipeline_status=json.dumps(pipeline_status))

                                            img.close()

                                            allDetected.append({
                                                "object_type": data.get('object'),
                                                'score': data.get('score'),
                                                'image_file': other_image_file,
                                                'temp_image': saveto,
                                            })
                                except Exception as e:
                                    print(e)
                                    print('--failing appending to allDetected other index of detection [online model]--')
                                    continue
                            
                            # # Loop End for all score
                            print(allDetected)
                            
                            # Return Object detected type
                            return allDetected
            
            if no_temp:
                pipeline_status = {}
                try:
                    pipeline_status = json.loads(image_file.pipeline_status)
                except Exception as e:
                    pipeline_status = {}
                label = detect_model
                pipeline_status['All Detected'] = pipeline_status.get('All Detected',[])
                image_file.pipeline_status = json.dumps(pipeline_status)
                image_file.save()

            resized_image_open.close()
            os.remove(saveto)
            print('Object Detect False, either bad response, no index, bad format array, sorted score empty etc.')
            return False
        else:
            if saveto:
                os.remove(saveto)
            print('FAILED TO Detect Object - Check Token, Object Detect Model id and file existence.')
            return False

####################
### CALL AI TEST ###
####################
# Default on 1st Image Test check Classifier Ids 1
# If result is shouldContinue function passed then run test again with classifier ids 2 (in case of preprocess etc it will go next anyway)
def test_image(image_file, title=None, description=None, save_to_path=None, classifier_index=0, detected_as=None, detect_model=None, project=None, offline=False, force_object_type=None, ibm_api_key=False, ibm_service_url=None):
    if force_object_type and not detected_as: # Force object Type by api
        try:
            pipeline_status = {}
            pipeline_status['Force Object Type'] = {
                'score': '1',
                'result': force_object_type
            }
            image_file.pipeline_status = json.dumps(pipeline_status)
            image_file.object_type = force_object_type
            image_file.save()

            file_url = str(os.path.abspath(os.path.dirname(__name__))) + image_file.file.url
            if not os.path.exists(file_url):
                file_url = os.environ.get('PROJECT_FOLDER','') + image_file.file.url
            saveto = None
            img = Image.open(file_url)
            img = img.convert('RGB')
            # Save to temporary for temp use
            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
            if not os.path.exists(os.path.join('media/temp/')):
                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
            else:
                saveto = os.path.join('media/temp/', filename)
            img.save(saveto, format='JPEG', quality=90)

            detected_as = [{
                "object_type": force_object_type,
                'image_file': image_file,
                'temp_image': saveto,
            }]
        except Exception as e:
            print(e)
            print('--error at FORCE OBJECT TYPE image test--')
            return False
    else:
        if not detected_as:
            detected_as = detect_image(image_file, detect_model, offline=offline, ibm_api_key=ibm_api_key, ibm_service_url=ibm_service_url)
        
        if not detected_as or len(detected_as) <= 0:
            if save_to_path:
                os.remove(save_to_path)
            return False

    failed = 0
    passed = 0
    for single_detected_as in detected_as:
        object_type = single_detected_as.get('object_type')
        image_file = single_detected_as.get('image_file')
        save_to_path = single_detected_as.get('temp_image')
        
        print('Trying ' + str(classifier_index) + ' No. Classifier for ' + object_type)
        # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
        check_and_get_classifier_ids = classifier_list.searchList(project,object_type,index=classifier_index)
        classifier = Classifier.objects.filter(name=check_and_get_classifier_ids).all().first()
        # IF Offline Model is in this Classifier
        if classifier and classifier.offline_model:
            ################# PRE PROCESS ###################
            if(classifier.offline_model.preprocess and classifier.offline_model.model_format in ('py')): # PREPROCESS
                try:
                    saved_model = None
                    if not os.path.exists(os.path.join('media/offline_models/')):
                        saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+classifier.offline_model.filename()
                    else:
                        saved_model = os.path.join('media/offline_models/', classifier.offline_model.filename())
                    print('----running PREPROCESS offline model .py------')
                    import importlib
                    loader = importlib.machinery.SourceFileLoader('model', saved_model)
                    handle = loader.load_module('model')
                    img = cv2.imread(save_to_path)
                    result = handle.run(img) # Saved Model .py must have run function (see readme.md in /api)
                    cv2.imwrite(save_to_path, result) # Replace the save to path aka /temp image with preprocessed image
                    baseuri = base64.b64encode(cv2.imencode('.jpg', result)[1]).decode()
                    pipeline_status = {}
                    try:
                        pipeline_status = json.loads(image_file.pipeline_status)
                    except Exception as e:
                        pipeline_status = {}
                    
                    pipeline_status[classifier.offline_model.name] = {
                        'score': '1',
                        'result': 'Pre-Processed Success',
                        'image': 'data:image/jpg;base64,'+baseuri
                    }
                    image_file.pipeline_status = json.dumps(pipeline_status)
                    image_file.save()
                    # In preprocess continue to next classifier pipeline if it exists of course
                    print('PREPROCESS OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                    if classifier_index + 1 < classifier_list.lenList(project,object_type):
                        test_image(image_file, title, description, save_to_path, classifier_index + 1, [single_detected_as], detect_model, project, offline, force_object_type, ibm_api_key, ibm_service_url) #save_to_path=temp file
                    else:
                        print('No more pipeline')
                except Exception as e:
                    print(e)
                    print('Failed to run PREPROCESS .py Offline Model')
            ############ POST PROCESS #######################
            elif(classifier.offline_model.postprocess and classifier.offline_model.model_format in ('py')): # POSTPROCESS
                try:
                    saved_model = None
                    if not os.path.exists(os.path.join('media/offline_models/')):
                        saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+classifier.offline_model.filename()
                    else:
                        saved_model = os.path.join('media/offline_models/', classifier.offline_model.filename())
                    print('----running POSTPROCESS offline model .py------')
                    import importlib
                    loader = importlib.machinery.SourceFileLoader('model', saved_model)
                    handle = loader.load_module('model')
                    img = cv2.imread(save_to_path)
                    pipeline_status = {}
                    try:
                        pipeline_status = json.loads(image_file.pipeline_status)
                    except Exception as e:
                        pipeline_status = {}
                    result = handle.run(img,pipeline_status,image_file.score,image_file.result) # Saved Model .py must have run function (see readme.md in /api in postprocess classifier section)
                    
                    if result.get('score', False) and result.get('result', False):
                        pipeline_status[classifier.offline_model.name] = {
                            'score': result.get('score'),
                            'result': result.get('result'),
                            'message': result.get('message', '')
                        }
                        image_file.result = result.get('result')
                        image_file.score = result.get('score')
                        image_file.tested = True
                    
                    image_file.pipeline_status = json.dumps(pipeline_status)
                    image_file.save()
                    # If Break=True value passed by postprocess then stop the flow.
                    if not result.get('break', False) or shouldContinue(result.get('result','')):
                        print('PostProcess OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                        if classifier_index + 1 < classifier_list.lenList(project,object_type):
                            test_image(image_file, title, description, save_to_path, classifier_index + 1, [single_detected_as], detect_model, project, offline, force_object_type, ibm_api_key, ibm_service_url) #save_to_path=temp file
                        else:
                            print('No more pipeline')
                except Exception as e:
                    print(e)
                    print('Failed to run POSTPROCESS .py Offline Model')
            ############# NORMAL PROCESS to return [[]] ##########
            else:
                res = test_offline_image(save_to_path, classifier.offline_model)
                print(res)
                if res:
                    pipeline_status = {}
                    try:
                        pipeline_status = json.loads(image_file.pipeline_status)
                    except Exception as e:
                        pipeline_status = {}

                    if res.get('score',False) and res.get('result',False): # Set Score and Result/Class
                        image_file.score = res.get('score')
                        image_file.result = res.get('result')
                        pipeline_status[check_and_get_classifier_ids] = {
                            'score': res.get('score'),
                            'result': res.get('result')
                        }
                        image_file.pipeline_status = json.dumps(pipeline_status)
                        image_file.tested = True
                        image_file.save()

                    if shouldContinue(result.get('result','')):
                        print('OFFLINE CLASSIFIER NORMAL OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                        if classifier_index + 1 < classifier_list.lenList(project,object_type):
                            test_image(image_file, title, description, save_to_path, classifier_index + 1, [single_detected_as], detect_model, project, offline, force_object_type, ibm_api_key, ibm_service_url) #save_to_path=temp file
                        else:
                            print('No more pipeline')

            if(classifier_index <= 0):
                os.remove(save_to_path)
            # return True
            passed += 1
            continue
        
        # Else IF Not Test in Online Model
        elif ( os.path.exists(save_to_path) and classifier and classifier.best_ibm_api_key()
            and classifier_index < classifier_list.lenList(project,object_type)
            and check_and_get_classifier_ids ):

            resized_image_open = None
            status = 0
            classifier_ids = check_and_get_classifier_ids

            # IF Classifier is not Object Detection type
            if not classifier.is_object_detection:
                # Authenticate the IBM Watson API
                api_token = classifier.best_ibm_api_key()
                # post_data = {'classifier_ids': classifier_ids} # 'threshold': '0.15 -1'
                # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
                # print(auth_base)

                # post_header = {'Accept':'application/json','Authorization':auth_base}
                
                # Open the Temporarily Resized Image (save_to_path from param comes if looped through - NOTE: now comes from detected_at directly)
                if save_to_path: # Comes from param on next recursion
                    resized_image_open = open(save_to_path, 'rb')
                
                # post_files = {
                #     'images_file': resized_image_open,
                # }

                # UPDATED WATSON API
                authenticator = IAMAuthenticator(api_token)
                visual_recognition = VisualRecognitionV3(
                    version='2018-03-19',
                    authenticator=authenticator
                )

                visual_recognition.set_service_url(classifier.get_ibm_service_url())

                try:
                    response = visual_recognition.classify(
                        images_file=resized_image_open,
                        classifier_ids=[classifier_ids])
                    content = response.get_result()
                    status = response.get_status_code()
                except ApiException as ex:
                    status = False
                    print('IBM Response was BAD - (e.g. image too large - INFO BELOW)')
                    print(ex.message)
                    failed += 1
                    continue

                # DEPRECATED API
                # # Call the API
                # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v3/classify?version=2018-03-19', files=post_files, headers=post_header, data=post_data)
                # status = response.status_code
                # try:
                #     content = response.json()
                # except ValueError:
                #     # IBM Response is BAD
                #     print('IBM Response was BAD - (e.g. image too large)')
                #     # return False
                #     failed += 1
                #     continue
                
                print(status)
                print(content)
                # If success save the data
                if(status == 200 or status == '200' or status == 201 or status == '201'):
                    if(content and content['images'][0]['classifiers'][0]['classes']):
                        sorted_by_score = sorted(content['images'][0]['classifiers'][0]['classes'], key=lambda k: k['score'], reverse=True)
                        print(sorted_by_score)

                        pipeline_status = {}
                        try:
                            pipeline_status = json.loads(image_file.pipeline_status)
                        except Exception as e:
                            pipeline_status = {}

                        if(sorted_by_score and sorted_by_score[0]): # Set Score and Result/Class
                            image_file.score = sorted_by_score[0]['score']
                            image_file.result = sorted_by_score[0]['class']
                            pipeline_status[classifier_ids] = {
                                'score': sorted_by_score[0]['score'],
                                'result': sorted_by_score[0]['class']
                            }
                            image_file.pipeline_status = json.dumps(pipeline_status)
                        
                        image_file.tested = True
                        image_file.save()
                        resized_image_open.close()

                        if shouldContinue(sorted_by_score[0]['class']):
                            print('CLASSIFIER ONLINE OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                            if classifier_index + 1 < classifier_list.lenList(project,object_type):
                                test_image(image_file, title, description, save_to_path, classifier_index + 1, [single_detected_as], detect_model, project, offline, force_object_type, ibm_api_key, ibm_service_url) #save_to_path=temp file
                            else:
                                print('No more pipeline')

                        if(classifier_index <= 0):
                            os.remove(save_to_path)
                        # return True
                        passed += 1
                        continue
            elif status == 404 or classifier.is_object_detection: # Assume Detect Model
                res = detect_image(image_file, classifier_ids, offline=False, no_temp=True, ibm_api_key=classifier.ibm_api_key, ibm_service_url=classifier.get_ibm_service_url(), save_to_path=save_to_path) # Note: Detect_Model is classifier ids (if 404 condition i.e. 2nd parameter)
                # print(res)
                if resized_image_open:
                    resized_image_open.close()
                pipeline_status = {}
                try:
                    pipeline_status = json.loads(image_file.pipeline_status)
                except Exception as e:
                    pipeline_status = {}
                
                if res and len(res) > 0:
                    pipeline_status[classifier_ids] = {
                        'score': res[0].get('score',1),
                        'result': res[0].get('object_type','')
                    }
                    image_file.pipeline_status = json.dumps(pipeline_status)
                    image_file.tested = True
                    image_file.result = res[0].get('object_type','')
                    image_file.score = res[0].get('score',1)
                    image_file.save()
                else:
                    # No Response log pipeline
                    pipeline_status[classifier_ids] = {
                        'score': 0,
                        'result': ''
                    }
                    image_file.pipeline_status = json.dumps(pipeline_status)
                    image_file.tested = True
                    image_file.save()
                
                if classifier_index + 1 < classifier_list.lenList(project,object_type):
                    print('CLASSIFIER ONLINE [Detect Model Acting as Classifier] OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                    test_image(image_file, title, description, save_to_path, classifier_index + 1, [single_detected_as], detect_model, project, offline, force_object_type, ibm_api_key, ibm_service_url) #save_to_path=temp file
                else:
                    print('No more pipeline')

                if(classifier_index <= 0):
                    os.remove(save_to_path)
                # return True
                passed += 1
                continue
        else:
            print('FAILED TO TEST - Check Token, Classifier ids and file existence.')
            if(classifier_index <= 0):
                if save_to_path:
                    os.remove(save_to_path)
            # return False
            failed += 1
            continue

    if(classifier_index <= 0):
        print('Images tested in all Classifiers looping through all Object Detected')
    if failed:
        print('Failed: '+str(failed))
    print('Passed: '+str(passed))

    if passed > 0 and failed < passed:
        return True
    else:
        return False

def quick_test_image(image_file, classifier_ids, classifier=False):
    image_file_path = None
    ibm_api_key = classifier.best_ibm_api_key() if classifier else ''
    if ( (settings.IBM_API_KEY or ibm_api_key) and classifier_ids and image_file):
        # UPDATED WATSON API
        authenticator = IAMAuthenticator(ibm_api_key)
        visual_recognition = VisualRecognitionV3(
            version='2018-03-19',
            authenticator=authenticator
        )

        visual_recognition.set_service_url(classifier.get_ibm_service_url())

        if type(image_file) is InMemoryUploadedFile:
            image_file_path = image_file.open()
        else:
            image_file_path = open(image_file.temporary_file_path(), 'rb')

        print(image_file_path)

        try:
            response = visual_recognition.classify(
                images_file=image_file_path,
                classifier_ids=[classifier_ids])
            content = response.get_result()
            status = response.get_status_code()
        except ApiException as ex:
            print(ex.message)
            image_file_path.close()
            return False

        if(status == 200 or status == '200' or status == 201 or status == '201'):
            if(content and content['images'][0]['classifiers'][0]['classes']):
                sorted_by_score = sorted(content['images'][0]['classifiers'][0]['classes'], key=lambda k: k['score'], reverse=True)
                print(sorted_by_score)
                image_file_path.close()
                return {'data':sorted_by_score, 'score':sorted_by_score[0]['score'], 'result':sorted_by_score[0]['class']}
            else:
                print('NO DATA')
                image_file_path.close()
                return False
        else:
            return False


        # DEPRECATED API
        # # Authenticate the IBM Watson API
        # api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
        # post_data = {'classifier_ids': classifier_ids} # 'threshold': '0.15 -1'
        # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
        # print(auth_base)

        # post_header = {'Accept':'application/json','Authorization':auth_base}
        
        # if type(image_file) is InMemoryUploadedFile:
        #     image_file_path = image_file.open()
        # else:
        #     image_file_path = open(image_file.temporary_file_path(), 'rb')

        # print(image_file_path)
        
        # post_files = {
        #     'images_file': image_file_path,
        # }

        # # Call the API
        # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v3/classify?version=2018-03-19', files=post_files, headers=post_header, data=post_data)
        # status = response.status_code
        # try:
        #     content = response.json()
        # except ValueError:
        #     # IBM Response is BAD
        #     print('IBM Response was BAD - (e.g. image too large)')
        #     image_file_path.close()
        #     return False
        
        # print(status)
        # print(content)
        # # If success save the data
        # if(status == 200 or status == '200' or status == 201 or status == '201'):
        #     if(content['images'][0]['classifiers'][0]['classes']):
        #         sorted_by_score = sorted(content['images'][0]['classifiers'][0]['classes'], key=lambda k: k['score'], reverse=True)
        #         print(sorted_by_score)
        #         image_file_path.close()
        #         return {'data':sorted_by_score, 'score':sorted_by_score[0]['score'], 'result':sorted_by_score[0]['class']}
        #     else:
        #         print('NO DATA')
        #         image_file_path.close()
        #         return False
    else:
        print('FAILED TO TEST CLASSIFIER by Admin - Check Token, Classifier ids is ready and file existence is upload temp file.')
        return False

# README.md might be helpful
def quick_test_offline_image(image_file, classifier, direct_offline_model=False):
    if not image_file or not classifier:
        return False

    img = Image.open(image_file).resize((150, 150))
    x = np.array(img)/255.0

    offline_model = None
    if direct_offline_model:
        offline_model = classifier
    else:
        offline_model = classifier.offline_model

    saved_model = None
    if not os.path.exists(os.path.join('media/offline_models/')):
        saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+offline_model.filename()
    else:
        saved_model = os.path.join('media/offline_models/', offline_model.filename())
    
    # Single thread example for tensorflow #
    # session_conf = tf.compat.v1.ConfigProto(
    #     intra_op_parallelism_threads=1,
    #     inter_op_parallelism_threads=1)
    # sess = tf.compat.v1.Session(config=session_conf)
    # K.set_session(sess)

    try:
        offlineModelLabels = json.loads(offline_model.offline_model_labels)
    except Exception as e:
        print(e)
        offlineModelLabels = []

    # Check type of model
    # h5, hdf5, keras, py
    result = [[]]
    if offline_model.model_format in ('h5', 'hdf5', 'keras'): # tf.keras models
        try:
            new_model = tf.keras.models.load_model(saved_model)
            result = new_model.predict(x[np.newaxis, ...])
            if type(result) != list:
                result = result.tolist()
        except Exception as e:
            print(e)
            print('Failed to run h5,hdf5,kears Offline Model [Quick Test]')
    elif offline_model.model_format in ('py'): # python script
        # Trying to run saved offline .py model (loading saved py file using string name)
        try:
            print('----running saved offline model .py------')
            print(str(saved_model))
            import importlib, inspect
            loader = importlib.machinery.SourceFileLoader('model', saved_model)
            handle = loader.load_module('model')
            print('----required import modules in .py----')
            print([str(i[0]) for i in inspect.getmembers(handle, inspect.ismodule )])
            print('--------------------------------------')

            result = handle.run(img, offlineModelLabels) # Saved Model .py must have run function (see readme.md in /api)
            if type(result) is not list or len(result) <= 0:
                result = [[]]
                print('py local model -- BAD response (not list) [Quick Test]')
        except Exception as e:
            print(e)
            print('Failed to run .py Offline Model [Quick Test]')
    else:
        print('This Offline Model Format is not supported')

    data = []
    
    i = 0
    for r in result[0]:
        if len(offlineModelLabels) > i:
            label = offlineModelLabels[i]
        else:
            label = 'No.'+str(i+1)

        data.append({
            "class": label,
            "score": r
        })
        i += 1

    result_type = ''
    score = '0'
    if len(result[0]) > 0:
        try:
            result_type = offlineModelLabels[result[0].index(max(result[0]))].title()
        except:
            result_type = 'no.'+str(result[0].index(max(result[0])) + 1)
        finally:
            score = max(result[0])
    
    tf.keras.backend.clear_session()
    # tf.reset_default_graph()
    return {'data':data, 'score':score, 'result':result_type}

# QUICK TEST Offline Images (classifier) - PRE-PROCESS / POST-PROCESS
def quick_test_offline_image_pre_post(image_file, classifier, request, fake_score=0, fake_result="", direct_offline_model=False):
    if not image_file or not classifier:
        return False

    img = cv2.imdecode(np.fromstring(image_file.read(), np.uint8), cv2.IMREAD_UNCHANGED)

    offline_model = None
    if direct_offline_model:
        offline_model = classifier
    else:
        offline_model = classifier.offline_model

    saved_model = None
    if not os.path.exists(os.path.join('media/offline_models/')):
        saved_model = os.environ.get('PROJECT_FOLDER','') + '/media/offline_models/'+offline_model.filename()
    else:
        saved_model = os.path.join('media/offline_models/', offline_model.filename())

    if offline_model.model_format in ('py') and saved_model: # python script
        # Trying to run saved offline .py model (loading saved py file using string name)
        try:
            print('----running quick test pre/post offline model .py------')
            import importlib, inspect
            loader = importlib.machinery.SourceFileLoader('model', saved_model)
            handle = loader.load_module('model')
            result = None
            if offline_model.preprocess:
                result = handle.run(img)
                baseuri = base64.b64encode(cv2.imencode('.jpg', result)[1]).decode()
                messages.success(request, "Detected as Pre-Process")
                return {"image": baseuri}
            elif offline_model.postprocess:
                messages.success(request, "Detected as Post-Process (Passing Empty Pipeline Data)")
                result = handle.run(img, {}, fake_score, fake_result)
                return {"data": result}
        except Exception as e:
            print(e)
            print('Failed to run quick test pre/post .py Offline Model [Quick Test]')
    else:
        messages.error(request, "Not a valid Offline Model (Although, marked Pre/Post Process is not .py format)")
        return False

# QUICK TEST DETECT MODE:
def quick_test_detect_image(image_file, detect_model, offline=False, project_folder='', ibm_api_key=False, ibm_service_url=None):
    MIN_SCORE_REQUIRED = 0.1
    # Find Image Path (used to open)
    file_url = None

    if type(image_file) is InMemoryUploadedFile:
        file_url = image_file.open()
    else:
        file_url = open(image_file.temporary_file_path(), 'rb')
    print('Detecting Image Object...Test')
    saveto = None

    # IF Is offline Model and detect model is given (detect_model = offline_model object)
    if offline and detect_model and file_url:
        print('Detecting Image Object [Offline Model]...')
        res = test_offline_image(file_url, detect_model)
        if res:
            # MULTIPLE OBJECT_TYPE ARE DETECTED THEN ALL ARE CROPPED AND SAVED AS IMAGE_FILE
            # Loop through all data[{class:'',score:''}]
            allDetected = []
            if res.get('data', False) and len(res.get('data')) > 0: # If res.data exists
                resdata = sorted(res.get('data'), key=itemgetter('score'), reverse=True)

                i = 0
                for data in resdata:
                    try:
                        if data.get('class', False) and data.get('score', False) and float(data.get('score')) >= MIN_SCORE_REQUIRED:
                            if not saveto or data.get('location', False):
                                # Open the file_url image
                                img = Image.open(file_url)
                                img = img.convert('RGB')
                                w, h = img.size
                                if data.get('location', False):
                                    img = img.crop(( data.get('location').get('left', 0), data.get('location').get('top', 0), data.get('location').get('width', w), data.get('location').get('height', h) ))
                                    # Crop if required
                                # Save to temporary for temp use
                                filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
                                if not os.path.exists(os.path.join('media/temp/')):
                                    saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                                else:
                                    saveto = os.path.join('media/temp/', filename)
                                
                                img.save(saveto, format='JPEG', quality=90)

                            pipeline_status = {}
                            pipeline_status = {
                                'score': data.get('score'),
                                'result': data.get('class'),
                                'location': data.get('location',{})
                            }

                            # Only for 1st detect (update original image_file & for other new other_image_file is created)
                            allDetected.append({ # add 0th item to default image_file
                                "object_type": data.get('class'),
                                'temp_image': saveto.replace(project_folder,'')+'?'+str(i),
                                'pipeline': pipeline_status
                            })

                            i += 1
                            img.close()
                    except Exception as e:
                        print(e)
                        print('--failing appending to allDetected other index of detection--')
                        continue
            
            # Loop End for all score
            print(allDetected)
            return allDetected
            
        else:
            return False
    else:
        # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
        if file_url and (ibm_api_key or settings.IBM_API_KEY) and (classifier_list.detect_object_model_id or detect_model) and ibm_service_url:
            object_id = classifier_list.detect_object_model_id
            if detect_model:
                object_id = detect_model

            # Authenticate the IBM Watson API
            api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
            # post_data = {'collection_ids': object_id, 'features':'objects', 'threshold':'0.15'} # 'threshold': '0.15 -1'
            # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
            # post_header = {'Accept':'application/json','Authorization':auth_base}
            resized_image_open = file_url
            
            # post_files = {
            #     'images_file': resized_image_open,
            # }

            # UPDATED WATSON API
            authenticator = IAMAuthenticator(api_token)
            visual_recognition = VisualRecognitionV4(
                version='2019-02-11',
                authenticator=authenticator
            )

            visual_recognition.set_service_url(ibm_service_url)

            try:
                response = visual_recognition.analyze(
                    collection_ids=[object_id],
                    features=[AnalyzeEnums.Features.OBJECTS.value],
                    images_file=[
                        FileWithMetadata(resized_image_open)
                    ])
                content = response.get_result()
                status = response.get_status_code()
            except ApiException as ex:
                print('IBM Response was BAD (During Detect) - (e.g. image too large)')
                print(ex.message)
                return False

            # DEPRECATED API
            # # Call the API
            # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v4/analyze?version=2019-02-11', files=post_files, headers=post_header, data=post_data)
            # status = response.status_code
            # try:
            #     content = response.json()
            # except ValueError:
            #     # IBM Response is BAD
            #     print('IBM Response was BAD (During Detect) - (e.g. image too large)')
            #     return False
            
            print(status)
            print(content)
            # If success save the data
            if(status == 200 or status == '200' or status == 201 or status == '201'):
                if "collections" in content['images'][0]['objects']:
                    if(content['images'][0]['objects']['collections'][0]['objects']):
                        sorted_by_score = sorted(content['images'][0]['objects']['collections'][0]['objects'], key=lambda k: k['score'], reverse=True)
                        print(sorted_by_score)
                        if(sorted_by_score and sorted_by_score[0]): # Set Score`
                            # MULTIPLE OBJECT_TYPE ARE DETECTED THEN ALL ARE CROPPED AND SAVED AS IMAGE_FILE
                            # Loop through all ...[objects]
                            allDetected = []
                            i = 0

                            for data in sorted_by_score: # from 1 (0 already added with default image_file above)
                                try:
                                    if data.get('object', False) and data.get('score', False) and float(data.get('score')) >= MIN_SCORE_REQUIRED:
                                        if not saveto or data.get('location', False):
                                            img = Image.open(file_url)
                                            img = img.convert('RGB')
                                            w, h = img.size
                                            if data.get('location', False):
                                                img = img.crop(( data.get('location').get('left', 0), data.get('location').get('top', 0), data.get('location').get('left', 0)+data.get('location').get('width', w), data.get('location').get('top', 0)+data.get('location').get('height', h) ))
                                            
                                            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
                                            if not os.path.exists(os.path.join('media/temp/')):
                                                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                                            else:
                                                saveto = os.path.join('media/temp/', filename)
                                            
                                            img.save(saveto, format='JPEG', quality=90)
                                            img.close()

                                        pipeline_status = {}
                                        # Add Pipeline detected detail (Note: old pipeline replaced if new detect model is called upon it)
                                        pipeline_status = {
                                            'score': data.get('score'),
                                            'result': data.get('object'),
                                            'location': data.get('location', {})
                                        }

                                        # Only for 1st detect (update original image_file & for other new other_image_file is created)
                                        allDetected.append({ # add 0th item to default image_file
                                            "object_type": data.get('object'),
                                            'temp_image': saveto.replace(project_folder,'')+'?'+str(i),
                                            'pipeline': pipeline_status
                                        })

                                        i += 1
                                except Exception as e:
                                    print(e)
                                    print('--failing appending to allDetected other index of detection [online model]--')
                                    continue
                            
                            # # Loop End for all score
                            print(allDetected)
                            
                            # Return Object detected type
                            return allDetected
            
            # ALSO SAVE TEMP IMAGE EVEN IF FAILED OR NOT DETECTED
            img = Image.open(file_url)
            img = img.convert('RGB')
            filename = '{}.{}'.format(uuid.uuid4().hex, 'jpg')
            if not os.path.exists(os.path.join('media/temp/')):
                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
            else:
                saveto = os.path.join('media/temp/', filename)
            img.save(saveto, format='JPEG', quality=90)
            img.close()
            resized_image_open.close()
            print('Object Detect False, either bad response, no index, bad format array, sorted score empty etc.')
            return {"data": content, "error": True, 'temp_image': saveto.replace(project_folder,'')+'?1'}
        else:
            print('FAILED TO Detect Object - Check Token, Object Detect Model id, IBM Service URL and file existence.')
            return False

#################################################
# ZIP and Pass Images to IBM watson for re-training
# Funcion receives the image file list, object(wall,rebar,etc.) and result(go,nogo,etc.)
def retrain_image(image_file_list, project, object_type, result, media_folder='image', classifier=None,  process=False, rotate=False, warp=False, inverse=False, noIndexCheck=False, request=False):
    zipObj = None
    zipPath = None
    all_transformed_image = []
    projectModel = Projects.objects.filter(project_name__icontains=project.split('-')[0]).all().first()
    try:
        # ZIP THE IMAGES #
        filename = '{}.{}'.format(uuid.uuid4().hex, 'zip')
        zipPath = os.path.join('media/temp/', filename)

        if not os.path.exists(os.path.join('media/temp/')):
            zipPath = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
        else:
            zipPath = os.path.join('media/temp/', filename)

        print(zipPath)
        zipObj = ZipFile(zipPath, 'w')

        ##############
        saveto = None # for transformed images
        if not os.path.exists(os.path.join('media/temp/')):
            saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'
        else:
            saveto = os.path.join('media/temp/')
        ##############

        # Add multiple files to the zip
        for image_file in image_file_list:
            #########PROCESS########
            # IF REQUEST CAME ALONG TO PROCESS THE IMAGES i.e. rotate h,v,-1 and zip them all
            if process:
                img = cv2.imread(image_file) # cv2 read image
                ext = pathlib.Path(image_file).suffix
                # print(img)
                print(ext)
                print('--CREATE CLASSIFIER PROCESS IMAGE AND RETURN LISTS')
                transformed_images = transform_image(img, ext, saveto, rotate, warp, inverse) # Call Transform Image function to do image processing with parameter options
                all_transformed_image = all_transformed_image + transformed_images # Transform IMAGES if requested
                for image in transformed_images:
                    zipObj.write(os.path.join(settings.BASE_DIR ,settings.MEDIA_ROOT,media_folder,os.path.basename(image)), os.path.basename(image))
                
            zipObj.write(os.path.join(settings.BASE_DIR ,settings.MEDIA_ROOT,media_folder,os.path.basename(image_file)), os.path.basename(image_file))
        
        # close the Zip File
        zipObj.close()
    except Exception as e:
        print(e)
        if zipObj and zipPath:
            zipObj.close()
            os.remove(zipPath)
        for image in all_transformed_image:
            os.remove(image)
        return False
    
    zipObj.close()
    # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
    if ( os.path.exists(zipPath)
        and (classifier_list.searchList(project,object_type,classifier) or noIndexCheck) ):

        zipObj = open(zipPath, 'rb')
        post_files = {}
        negative_post_files = None

        if result.lower() == 'negative':
            negative_post_files = zipObj
        else:
            post_files = {
                result: zipObj,
            }

        passed = 0
        offline = 0

        for classifier_ids in classifier_list.value().get(project,{}).get(object_type,[]):
            this_classifier = Classifier.objects.filter(name=classifier_ids).filter(project=projectModel).all().first()
            # Check if classifier is offline
            if this_classifier.offline_model:
                offline += 1
            
            api_token = this_classifier.best_ibm_api_key()
            # # Authenticate the IBM Watson API
            # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
            # print(auth_base)
            # post_header = {'Accept':'application/json','Authorization':auth_base}

            # Check if specific classifier to re-train on (and continue if not equal to it)
            if(classifier and classifier != 'all'):
                if(classifier_ids != classifier):
                    continue

            # UPDATED WATSON API
            authenticator = IAMAuthenticator(api_token)
            visual_recognition = VisualRecognitionV3(
                version='2018-03-19',
                authenticator=authenticator
            )

            visual_recognition.set_service_url(this_classifier.get_ibm_service_url())

            try:
                response = visual_recognition.update_classifier(classifier_id=classifier_ids,
                    positive_examples=post_files,
                    negative_examples=negative_post_files)
                content = response.get_result()
                print(json.dump(content), indent=2)
                status = response.get_status_code()
            except ApiException as ex:
                print(ex.message)
                status = False

            # DEPRECATED API
            # # Call the API
            # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v3/classifiers/'+classifier_ids+'?version=2018-03-19', files=post_files, headers=post_header)
            # status = response.status_code
            # try:
            #     content = response.json()
            # except ValueError:
            #     # IBM Response is BAD
            #     print(response)
            #     print('IBM Response was BAD - (e.g. zip might be too large)')
            
            # print(status)
            # print(content)
            # If success save the data
            if(status == 200 or status == '200' or status == 201 or status == '201'):
                passed += 1
        
        zipObj.close()
        os.remove(zipPath)
        print(str(len(all_transformed_image)) + ' transformed images...')
        for image in all_transformed_image:
            os.remove(image)

        if(offline > 0 and request):
            messages.warning(request, str(offline) +' Classifier(s) found where Offline Model and is ignored. (Offline Model does not require to be re-trained)')
        
        # IF PASSED AT LEAST ONE CLASSIFIER THEN "OK"
        if(passed > 0):
            return passed
        else:
            return False
    else:
        print('FAILED TO TEST - Check Token, Classifier ids, Watson Service URL and file existence.')
        return False

#################################################
# Create New classifier
# User uploades proper zip file with classifier name
def create_classifier(zip_file_list, negative_zip=False, name=False, object_type=False, process=False, rotate=False, warp=False, inverse=False, ibm_api_key=False, project=False, ibm_service_url=None):
    # IF IBM KEY is provided (also check zip_file_list is ok)
    if ( (ibm_api_key or settings.IBM_API_KEY) and zip_file_list and name and object_type and ibm_service_url ):
        # Authenticate the IBM Watson API
        if not ibm_api_key and project:
            project = Projects.objects.get(id=project)
            ibm_api_key = project.ibm_api_key

        api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
        # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
        # print(auth_base)
        # post_header = {'Accept':'application/json','Authorization':auth_base}
        post_files = {}
        negative_post_files = None
        bad_zip = 0
        all_unzipped_images = []
        all_zipped_image = []
        all_custom_zip = []
        files_left_to_close = []
        x = None # ZIP FILE OPEN VARIABLE

        for zip_file in zip_file_list:
            all_unzipped_images = []
            kind = filetype.guess(zip_file)
            if kind is None or kind.extension != 'zip' :
                print(kind.extension)
                print('Cannot guess file type or is not a ZIP file!')
                bad_zip += 1
            else:
                if not zip_file.name:
                    print('Zip file has no name, weird but true!')
                    bad_zip += 1
                else:
                    if type(zip_file) is InMemoryUploadedFile:
                        x = zip_file.open()
                    else:
                        x = open(zip_file.temporary_file_path(), 'rb')
                    
                    #########PROCESS########
                    # IF REQUEST CAME ALONG TO PROCESS THE IMAGES i.e. rotate h,v,-1 and zip them all
                    if process:
                        print('--CREATE CLASSIFIER PROCESS IMAGE AND ZIP')
                        ######
                        z = ZipFile(x) # zipfile used
                        
                        for zipinfo in z.infolist(): # Loop on all zipfile info list content (assume zip file has image files alone)
                            ext = pathlib.Path(zipinfo.filename).suffix if pathlib.Path(zipinfo.filename).suffix else '.jpg' # get extension
                            filename = '{}{}'.format(uuid.uuid4().hex, ext) # generate filename

                            saveto = None
                            if not os.path.exists(os.path.join('media/temp/')):
                                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'
                            else:
                                saveto = os.path.join('media/temp/')

                            zipinfo.filename = filename # replace filename
                            extracted = z.extract(zipinfo, saveto) # extract and save to temp

                            if extracted:
                                img = cv2.imread(saveto + filename) # cv2 read image
                                all_unzipped_images.append(saveto + filename) # add image to array (original image)
                                transformed_images = transform_image(img, ext, saveto, rotate, warp, inverse) # Call Transform Image function to do image processing with parameter options
                                all_unzipped_images = all_unzipped_images + transformed_images

                        # AFTER ALL ARE PROCESSED AND ZIP in ONE zip file
                        print(all_unzipped_images)
                        # IF PROCESSED IMAGES EXISTS THEN ZIP THEM AND SEND TO post_files
                        if all_unzipped_images and process:
                            zipObj = None
                            zipPath = None
                            try:
                                # ZIP THE IMAGES #
                                filename = '{}.{}'.format(uuid.uuid4().hex, 'zip')
                                zipPath = os.path.join('media/temp/', filename)

                                if not os.path.exists(os.path.join('media/temp/')):
                                    zipPath = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
                                else:
                                    zipPath = os.path.join('media/temp/', filename)

                                print(zipPath)
                                zipObj = ZipFile(zipPath, 'w')
                                # Add multiple files to the zip
                                for image_file in all_unzipped_images:
                                    zipObj.write(os.path.join(settings.BASE_DIR ,settings.MEDIA_ROOT,'temp',os.path.basename(image_file)), os.path.basename(image_file))
                                # close the Zip File
                                zipObj.close()

                                x = open(zipPath, 'rb')
                                all_custom_zip.append(zipPath) # add zip to array (used later to delete from temp)
                                # add image to post files
                                # post_files[zip_file.name.replace('.zip','')+'_positive_examples'] = x # Deprecated
                                post_files[zip_file.name.replace('.zip','')] = x
                                files_left_to_close.append(x) # add files left to close to array (used later to close before deleting)
                            except Exception as e:
                                print(e)
                                if zipObj and zipPath:
                                    all_zipped_image = all_zipped_image + all_unzipped_images
                                    zipObj.close()
                                    os.remove(zipPath)
                                    x.close()
                                    for f in files_left_to_close:
                                        f.close()
                                    for image in all_zipped_image:
                                        os.remove(image)
                                    for zip in all_custom_zip:
                                        os.remove(zip)
                                return False
                            
                            if zipObj:
                                zipObj.close()

                            all_zipped_image = all_zipped_image + all_unzipped_images
                    else: # If process is not provided via admin just upload the zip given by user
                        # post_files[zip_file.name.replace('.zip','')+'_positive_examples'] = x # Deprecated
                        post_files[zip_file.name.replace('.zip','')] = x
        
        print(post_files)

        #######################
        # TO STOP FOR TESTING #
        # for f in files_left_to_close:
        #     f.close()
        # for image in all_zipped_image:
        #     os.remove(image)
        # for zip in all_custom_zip:
        #     os.remove(zip)
        # return False
        #######################

        if negative_zip:
            x = None
            if type(negative_zip) is InMemoryUploadedFile:
                x = negative_zip.open()
            else:
                x = open(negative_zip.temporary_file_path(), 'rb')
            
            # post_files['negative_examples'] = x # Deprecated
            negative_post_files = x
            print(negative_post_files)

        # post_data = {'name': name}

        # UPDATED WATSON API
        authenticator = IAMAuthenticator(api_token)
        visual_recognition = VisualRecognitionV3(
            version='2018-03-19',
            authenticator=authenticator
        )

        visual_recognition.set_service_url(ibm_service_url)

        try:
            response = visual_recognition.create_classifier(name,
                positive_examples=post_files,
                negative_examples=negative_post_files)
            content = response.get_result()
            status = response.get_status_code()
        except ApiException as ex:
            print(ex.message)
            status = False


        # DEPRECATED API
        # # Call the API
        # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v3/classifiers?version=2018-03-19', files=post_files, headers=post_header, data=post_data)
        # status = response.status_code
        # try:
        #     content = response.json()
        # except ValueError:
        #     # IBM Response is BAD
        #     print(response)
        #     print('IBM Response was BAD - (e.g. zip might be too large or similar problem)')
        
        # print(status)
        # print(content)

        x.close()
        for f in files_left_to_close:
            f.close()
        for image in all_zipped_image:
            os.remove(image)
        for zip in all_custom_zip:
            os.remove(zip)
        
        # If success save the data
        if(status == 200 or status == '200' or status == 201 or status == '201'):
            reload_classifier_list()
            return {'data': content, 'bad_zip': bad_zip}
        
        return False
    else:
        print('FAILED TO TEST - Check Token, Classifier Name, Zip files, IBM Service URL etc. exists or not')
        return False

# Fetch Classifier Details #
def classifier_detail(project, object_type, model):
    # IF IBM KEY is provided + classifier list exists
    if ( classifier_list.searchList(project, object_type, model) ):

        classifier = Classifier.objects.filter(name=model).all().first()
        # IF IS OBJECT DETECTION ACTING AS CLASSIFER:
        if classifier.is_object_detection:
            detail = object_detail(classifier.name, classifier.best_ibm_api_key(), classifier.get_ibm_service_url())
            if detail:
                return detail
            else:
                return False

        if classifier.offline_model:
            try:
                offlineModelLabels = json.loads(classifier.offline_model.offline_model_labels)
            except Exception as e:
                offlineModelLabels = []
            return {
                'offline': True,
                'name': classifier.name,
                'type': classifier.offline_model.model_type,
                'format': classifier.offline_model.model_format,
                'labels': offlineModelLabels,
                'url': classifier.offline_model.file.url
            }

        # UPDATED WATSON API
        authenticator = IAMAuthenticator(classifier.best_ibm_api_key())
        visual_recognition = VisualRecognitionV3(
            version='2018-03-19',
            authenticator=authenticator
        )

        visual_recognition.set_service_url(classifier.get_ibm_service_url())

        try:
            response = visual_recognition.get_classifier(classifier_id=model)
            content = response.get_result()
            status = response.get_status_code()
        except ApiException as ex:
            print(ex.message)
            status = False

        if(status == 200 or status == '200' or status == 201 or status == '201'):
            return content
        else:
            return False

        # DEPRECATED API
        # # Authenticate the IBM Watson API
        # api_token = classifier.best_ibm_api_key()
        # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
        # print(auth_base)
        # post_header = {'Accept':'application/json','Authorization':auth_base}

        # # Call the API
        # try:
        #     response = requests.get('https://gateway.watsonplatform.net/visual-recognition/api/v3/classifiers/'+model+'?version=2018-03-19', headers=post_header)
        #     status = response.status_code
        # except Exception as e:
        #     print(e)
        #     response = {}
        #     status = False
        
        # try:
        #     content = response.json()
        # except ValueError:
        #     # IBM Response is BAD
        #     print('IBM Response was BAD')
        
        # print(status)
        # print(content)
        # # If success save the data
        # if(status == 200 or status == '200' or status == 201 or status == '201'):
        #     return content
        # else:
        #     return False

# Fetch Object Detection Metadata Details #
def object_detail(object_id, ibm_api_key=False, ibm_service_url=None):
    # IF IBM KEY is provided + classifier list exists
    if ( (ibm_api_key or settings.IBM_API_KEY)
        and (classifier_list.detect_object_model_id or object_id) and ibm_service_url ):
        
        if not object_id:
            object_id = classifier_list.detect_object_model_id

        # Authenticate the IBM Watson API
        api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
        # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
        # print(auth_base)
        # post_header = {'Accept':'application/json','Authorization':auth_base}
        data = {}

        # UPDATED WATSON API
        authenticator = IAMAuthenticator(api_token)
        visual_recognition = VisualRecognitionV4(
            version='2019-02-11',
            authenticator=authenticator
        )

        visual_recognition.set_service_url(ibm_service_url)

        # GET Collection Detail
        try:
            response = visual_recognition.get_collection(collection_id=object_id)
            content = response.get_result()
            print(content)
            status = response.get_status_code()
        except ApiException as ex:
            print(ex.message)
            content = {}
            status = False

        data.update(content)

        # GET Objects List
        try:
            response = visual_recognition.list_object_metadata(collection_id=object_id)
            content = response.get_result()
            status = response.get_status_code()
        except ApiException as ex:
            print(ex.message)
            content = {}
            status = False
        
        data.update(content)
        print(data)

        # Deprecated API
        # # Call the API
        # try:
        #     response = requests.get('https://gateway.watsonplatform.net/visual-recognition/api/v4/collections/'+object_id+'?version=2019-02-11', headers=post_header)
        #     status = response.status_code
        # except Exception as e:
        #     print(e)
        #     response = {}
        #     status = False

        # try:
        #     content.update(response.json())
        # except ValueError:
        #     # IBM Response is BAD
        #     print('IBM Response was BAD for collection info')

        # Call the API
        # try:
        #     response = requests.get('https://gateway.watsonplatform.net/visual-recognition/api/v4/collections/'+object_id+'/objects?version=2019-02-11', headers=post_header)
        #     status = response.status_code
        # except Exception as e:
        #     print(e)
        #     response = {}
        #     status = False

        # try:
        #     content.update(response.json())
        # except ValueError:
        #     # IBM Response is BAD
        #     print('IBM Response was BAD for objects')

        # If success save the data
        if(data and status == 200 or status == '200' or status == 201 or status == '201'):
            return data
            
    return False

# Similar to detect_image but from temp no need to deal with image_file model (used in e.g. google map image test detect)
def detect_temp_image(file_url, detect_model, offline=False, ibm_api_key=False, ibm_service_url=None):
    # IF Is offline Model and detect model is given (detect_model = offline_model object)
    if offline and detect_model and os.path.exists(file_url):
        print('Detecting Image Object [Offline Model] [TEMP Google Street Images]...')
        res = test_offline_image(file_url, detect_model)
        allDetected = []
        if res and res.get('data', False) and len(res.get('data')) > 0:
            resdata = sorted(res.get('data'), key=itemgetter('score'), reverse=True)
            for data in resdata:
                pipeline_status = {
                    'score': data.get('score','0'),
                    'result': data.get('class','None'),
                    'location': data.get('location',{})
                }
                allDetected.append({ # add 0th item to default image_file
                    "object_type": data.get('class','None'),
                    'temp_image': file_url,
                    'file_url': file_url,
                    'pipeline': pipeline_status
                })

            return allDetected
        else:
            return False
    else:
        # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
        print('Detecting Image Object [TEMP Google Street Images]...')
        saveto = None
        if os.path.exists(file_url) and (ibm_api_key or settings.IBM_API_KEY) and (classifier_list.detect_object_model_id or detect_model) and ibm_service_url:
            object_id = classifier_list.detect_object_model_id
            if detect_model:
                object_id = detect_model
            # Authenticate the IBM Watson API
            api_token = ibm_api_key if ibm_api_key else str(settings.IBM_API_KEY)
            # post_data = {'collection_ids': object_id, 'features':'objects', 'threshold':'0.15'} # 'threshold': '0.15 -1'
            # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
            # print(auth_base)

            # post_header = {'Accept':'application/json','Authorization':auth_base}
            
            # Temporary Resized Image (basewidth x calcheight)(save_to_path from param comes if looped through)
            basewidth = 500
            temp = Image.open(file_url)
            wpercent = (basewidth/float(temp.size[0]))
            hsize = int((float(temp.size[1])*float(wpercent)))
            temp = temp.resize((basewidth,hsize), Image.ANTIALIAS)
            ext = file_url.split('.')[-1]
            filename = '{}.{}'.format(uuid.uuid4().hex, ext)

            if not os.path.exists(os.path.join('media/temp/')):
                saveto = os.environ.get('PROJECT_FOLDER','') + '/media/temp/'+filename
            else:
                saveto = os.path.join('media/temp/', filename)

            print(saveto)
            
            temp.save(saveto)
            resized_image_open = open(saveto, 'rb')
            
            # post_files = {
            #     'images_file': resized_image_open,
            # }

            # UPDATED WATSON API
            authenticator = IAMAuthenticator(api_token)
            visual_recognition = VisualRecognitionV4(
                version='2019-02-11',
                authenticator=authenticator
            )

            visual_recognition.set_service_url(ibm_service_url)

            try:
                response = visual_recognition.analyze(
                    collection_ids=[object_id],
                    features=[AnalyzeEnums.Features.OBJECTS.value],
                    images_file=[
                        FileWithMetadata(resized_image_open)
                    ])
                content = response.get_result()
                status = response.get_status_code()
            except ApiException as ex:
                print('IBM Response was BAD (During Detect in GOOGLE MAP) - (e.g. image too large)')
                print(ex.message)
                return False

            # DEPRECATED API
            # # Call the API
            # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v4/analyze?version=2019-02-11', files=post_files, headers=post_header, data=post_data)
            # status = response.status_code
            # try:
            #     content = response.json()
            # except ValueError:
            #     # IBM Response is BAD
            #     print('IBM Response was BAD (During Detect) - (e.g. image too large)')
            #     return False
            
            print(status)
            print(content)
            # If success save the data
            if(status == 200 or status == '200' or status == 201 or status == '201'):
                if "collections" in content['images'][0]['objects']:
                    if(content['images'][0]['objects']['collections'][0]['objects']):
                        sorted_by_score = sorted(content['images'][0]['objects']['collections'][0]['objects'], key=lambda k: k['score'], reverse=True)
                        print(sorted_by_score)
                        if(sorted_by_score and sorted_by_score[0]): # Set Score
                            resized_image_open.close()
                            allDetected = []

                            for data in sorted_by_score: # from 1 (0 already added with default image_file above)
                                try:
                                    if data.get('object', False) and data.get('score', False):
                                        pipeline_status = {}
                                        # Add Pipeline detected detail (Note: old pipeline replaced if new detect model is called upon it)
                                        pipeline_status = {
                                            'score': data.get('score','0'),
                                            'result': data.get('object','None'),
                                            'location': data.get('location', {})
                                        }

                                        # Only for 1st detect (update original image_file & for other new other_image_file is created)
                                        allDetected.append({ # add 0th item to default image_file
                                            "object_type": data.get('object','None'),
                                            'temp_image': file_url,
                                            'file_url': file_url,
                                            'pipeline': pipeline_status
                                        })

                                except Exception as e:
                                    print(e)
                                    print('--failing appending to allDetected other index of detection [online model]--')
                                    continue
                            # Return Object detected type
                            return allDetected
            
            resized_image_open.close()
            os.remove(saveto)
            print('Object Detect False, either bad response, no index, bad format array, sorted score empty etc. [Google Street Temp]')
            return False
        else:
            if saveto:
                os.remove(saveto)
            print('FAILED TO Detect Object - Check Token, Object Detect Model id and file existence. [Google Street Temp]')
            return False

# THESE ARE GLOBAL VAR FOR TEST TEMP IMAGE USED DURING RECURSION
score = None
result = None
pipeline_status = {}
# Pipeline Status Format
# {
# 	'classifier_name': {
# 		'result': 'nogo',
# 		'score': 0.8,
# 	},
# }
### SAME AS test_image BUT FOR TEMP IMAGES (no need to deal with models and other stuffs (used for e.g. in google map images testing))
# Note not added preprocess postprocess codes
def test_temp_images(image_file, save_to_path=None, classifier_index=0, detected_as=None, detect_model=None, project=None, offline=False, ibm_api_key=False, ibm_service_url=None):
    global score, result, pipeline_status
    if not detected_as:
        detected_as = detect_temp_image(image_file, detect_model, offline=offline, ibm_api_key=ibm_api_key, ibm_service_url=ibm_service_url)
        print(detected_as)
    
    if not detected_as or len(detected_as) <= 0:
        if save_to_path:
            os.remove(save_to_path)
        return False
    
    failed = 0
    passed = 0

    object_type = detected_as[0].get('object_type')
    image_file = detected_as[0].get('file_url')
    save_to_path = detected_as[0].get('temp_image')
    
    print('Trying ' + str(classifier_index) + ' No. Classifier for ' + object_type)
    # IF OS Path to Image exists + IBM KEY is provided + classifier list exists
    check_and_get_classifier_ids = classifier_list.searchList(project,object_type,index=classifier_index)
    classifier = Classifier.objects.filter(name=check_and_get_classifier_ids).all().first()
    # IF Offline Model is in this Classifier
    if classifier and classifier.offline_model:
        # Ignore on preprocess/postprocess
        if classifier.offline_model.preprocess or classifier.offline_model.postprocess:
            if classifier_index + 1 < classifier_list.lenList(project,object_type):
                print('TEMP: FOR PRE/POST PROCESSOR - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                test_temp_images(image_file, save_to_path, classifier_index + 1, detected_as, detect_model, project, offline, ibm_api_key, ibm_service_url) #save_to_path=temp file
            else:
                print('No more pipeline (offline model)')
            return False

        res = test_offline_image(image_file, classifier.offline_model)
        # print(res)
        if res:
            score = res.get('score','')
            result = res.get('result','')
            i = 0
            for specific in detected_as:
                if i == 0:
                    pipeline_status['Detected '+specific.get('object_type')] = specific.get('pipeline',{})
                else:
                    pipeline_status[str(i)+' - '+'Also Detected '+specific.get('object_type')] = specific.get('pipeline',{})
                
                i += 1
            pipeline_status[check_and_get_classifier_ids] = {
                'score': res.get('score',''),
                'result': res.get('result','')
            }
            if shouldContinue(res.get('result','')):
                if classifier_index + 1 < classifier_list.lenList(project,object_type):
                    print('TEMP: OFFLINE CLASSIFIER OK  - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                    test_temp_images(image_file, save_to_path, classifier_index + 1, detected_as, detect_model, project, offline, ibm_api_key, ibm_service_url) #save_to_path=temp file
                else:
                    print('No more pipeline (offline model)')

            pipeline_status_copy = pipeline_status.copy()
            score_copy = score
            result_copy = result
            if(classifier_index <= 0):
                pipeline_status = {}
                score = None
                result = None
                # os.remove(save_to_path)
            return {'score': score_copy, 'result': result_copy, 'pipeline_status': pipeline_status_copy}
    
    # Else IF Not Test in Online Model
    elif ( os.path.exists(save_to_path) and classifier.best_ibm_api_key()
        and classifier_index < classifier_list.lenList(project,object_type)
        and check_and_get_classifier_ids ):

        # Authenticate the IBM Watson API
        api_token = classifier.best_ibm_api_key()
        classifier_ids = check_and_get_classifier_ids
        # post_data = {'classifier_ids': classifier_ids} # 'threshold': '0.15 -1'
        # auth_base = 'Basic '+str(base64.b64encode(bytes('apikey:'+api_token, 'utf-8')).decode('utf-8'))
        # print(auth_base)

        # post_header = {'Accept':'application/json','Authorization':auth_base}
        
        # Open the Temporarily Resized Image (save_to_path from param comes if looped through - NOTE: now comes from detected_at directly)
        if save_to_path: # Comes from param on next recursion
            resized_image_open = open(save_to_path, 'rb')
        
        # post_files = {
        #     'images_file': resized_image_open,
        # }

        # UPDATED WATSON API
        authenticator = IAMAuthenticator(api_token)
        visual_recognition = VisualRecognitionV3(
            version='2018-03-19',
            authenticator=authenticator
        )

        visual_recognition.set_service_url(classifier.get_ibm_service_url())

        try:
            response = visual_recognition.classify(
                images_file=resized_image_open,
                classifier_ids=[classifier_ids])
            content = response.get_result()
            status = response.get_status_code()
        except ApiException as ex:
            status = False
            print('IBM Response was BAD in GOOGLE MAP - (e.g. image too large - INFO BELOW)')
            print(ex.message)
            return False

        # DEPRECATED API
        # # Call the API
        # response = requests.post('https://gateway.watsonplatform.net/visual-recognition/api/v3/classify?version=2018-03-19', files=post_files, headers=post_header, data=post_data)
        # status = response.status_code
        # try:
        #     content = response.json()
        # except ValueError:
        #     # IBM Response is BAD
        #     print('IBM Response was BAD - (e.g. image too large)')
        #     return False
        
        print(status)
        print(content)
        # If success save the data
        if(status == 200 or status == '200' or status == 201 or status == '201'):
            if(content['images'][0]['classifiers'][0]['classes']):
                sorted_by_score = sorted(content['images'][0]['classifiers'][0]['classes'], key=lambda k: k['score'], reverse=True)
                # print(sorted_by_score)
                score = sorted_by_score[0]['score']
                result = sorted_by_score[0]['class']

                if(sorted_by_score and sorted_by_score[0]): # Set Score and Result/Class
                    i = 0
                    for specific in detected_as:
                        if i == 0:
                            pipeline_status['Detected '+specific.get('object_type')] = specific.get('pipeline',{})
                        else:
                            pipeline_status[str(i)+' - '+'Also Detected '+specific.get('object_type')] = specific.get('pipeline',{})
                        
                        i += 1
                    pipeline_status[check_and_get_classifier_ids] = {
                        'score': sorted_by_score[0]['score'],
                        'result': sorted_by_score[0]['class']
                    }

                if shouldContinue(sorted_by_score[0]['class']):
                    if classifier_index + 1 < classifier_list.lenList(project,object_type):
                        print('TEMP: ONLINE CLASSIFIER OK - PASSING THROUGH NEW MODEL CLASSIFIER #'+str(classifier_index + 1))
                        test_temp_images(image_file, save_to_path, classifier_index + 1, detected_as, detect_model, project, offline, ibm_api_key, ibm_service_url) #save_to_path=temp file
                    else:
                        print('No more pipeline')

                pipeline_status_copy = pipeline_status.copy()
                score_copy = score
                result_copy = result
                if(classifier_index <= 0):
                    pipeline_status = {}
                    score = None
                    result = None
                    resized_image_open.close()
                    # os.remove(save_to_path)
                return {'score': score_copy, 'result': result_copy, 'pipeline_status': pipeline_status_copy}
    else:
        print('FAILED TO TEST - Check Token, Classifier ids and file existence.')
        return False

# request: html request, path: path to file (e.g. api/README.md)[Never use '/' before the path like /api]
def markdownToHtml(request=None, path=None, title="Information Document"):
    try:
        if path:
            if not os.path.exists(os.path.join(path)):
                location = os.environ.get('PROJECT_FOLDER','') + '/' + path
            else:
                location = os.path.join('api/README.md')
            
            html = '<html><head><title>'+title+'</title><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="icon" type="image/png" href="/static/dist/img/favicon-32x32.png" sizes="32x32" /><link rel="icon" type="image/png" href="/static/dist/img/favicon-16x16.png" sizes="16x16" /></head><link rel="stylesheet" href="/static/dist/css/adminlte.min.css"/><link rel="stylesheet" href="//cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.2/styles/default.min.css"><script src="//cdnjs.cloudflare.com/ajax/libs/highlight.js/10.1.2/highlight.min.js"></script><body class="p-3">'
            html = html + mistune.html(open(location, "r").read())
            html = html + '<style>@keyframes blink{0%{opacity:0;}100%{opacity:1}}.blink{animation: blink 0.3s ease 7;}</style><script>hljs.initHighlightingOnLoad();</script></body></html>'
            return HttpResponse(html, 'text/html')
        else:
            return redirect('dashboard')
    except Exception as e:
        print(e)
        if request:
            messages.info(request, 'Failed to open Readme Help')
        return redirect('offline.model.create')