import json
from django.conf import settings

from django.db.models import Prefetch
from django.core.cache import cache

from projects.models import Projects

try:
    from api.models import Classifier, ObjectType
except ImportError as e:
    print(e)
    print('Classifier list model import error')

# NOTE: DETECT OBJECT MODEL ID FOR WATSON (IF ANY PROJECT CONTAINS detect model then that is used)
# NOTE: IF NO model is given to a project this will be the default DETECT MODEL ID
# NEEDS TO BE CHANGED AS REQUIRED - IN SERVER, PRODUCTION, STAGE as required
# detect_object_model_id = '9068cba3-6dab-4233-805b-2d64a16daae8' # Old v1
detect_object_model_id = '15b7b8e4-05c9-4eb1-bac4-11cfe884c7f3'
data_val = {}

# def classifier_list(): # Previous Name (now data function used for short name to enable reload())
#     pass

def data():
    global data_val
    classifier_list = {
        # 'dev_project': {
            # 'wall':[
            #     'IfNogo_778825345'
            # ],
            # 'rebar':[
            #     'DefaultCustomModel_1566448629',
            #     'IfNogo_778825345'
            # ],
        # },
    }

    try:
        projects = Projects.objects.order_by('created_at').all().prefetch_related(Prefetch('object_types', queryset=ObjectType.objects.order_by('created_at').all().prefetch_related(Prefetch('classifiers', queryset=Classifier.objects.order_by('-object_type','order')))))
        for project in projects:
            if not classifier_list.get(project.unique_name(), False):
                classifier_list[project.unique_name()] = {}

            if not project.object_types.all().count():
                if not settings.TESTING:
                    print('WARNING: No Object Type for ' + project.project_name)
            else:
                for object_type in project.object_types.all():
                    if object_type.name.lower() not in classifier_list.get(project.unique_name(),[]):
                        classifier_list[project.unique_name()][object_type.name.lower()] = []
                    
                    if not object_type.classifiers.all().count():
                        if not settings.TESTING:
                            print('WARNING: No Classifiers for ' + object_type.name + ' in ' + project.project_name)
                    else:
                        for classifier in object_type.classifiers.all():
                            if classifier.name not in classifier_list.get(project.unique_name(),[]).get(object_type.name.lower(),[]):
                                classifier_list[project.unique_name()][object_type.name.lower()] = classifier_list[project.unique_name()][object_type.name.lower()] + [classifier.name]

        print('-LOADING CLASSIFIER LIST-')
        # print(json.dumps(classifier_list, indent=4))
        data_val = classifier_list
        cache.set('classifier_cache', classifier_list, None)
        return classifier_list
    except Exception as e:
        #########
        print(e)
        print('Classifier List throwing Model exception - IF KEEPS REPEATING IT IS A PROBLEM (Once is OK)')
        cache.set('classifier_cache', classifier_list, None)
        return classifier_list

total_classifiers = len(data())
if(total_classifiers <= 0):
    print('-------------------------------------------------------------------------------------------')
    print('NO CLASSIFIERS MODEL TYPES PROVIDED')
    print('PLEASE EDIT isac_simo/classifier_list.py file and add model classifiers as required in list')
    print('OR Ask Admin user to train and add new classifier')
    print('-------------------------------------------------------------------------------------------')
else:
    print(str(total_classifiers) + ' Classifier Model Type Found.')

def value():
    global data_val
    return cache.get('classifier_cache', data_val)

def lenList(project, object_type):
    """
    Returns the length of data specific object (i.e. total pipeline steps)

    project = Project model instance .unique_name() property

    object_type = Lower cased ObjectType model .name property
    """
    global data_val
    content = cache.get('classifier_cache', data_val)
    if project and object_type and content.get(project, False):
        if content.get(project).get(object_type, False):
            return len(content.get(project).get(object_type))
    
    return 0

def searchList(project, object_type, model=None, index=-1):
    """
    Returns model name if provided model or index exists in that project's object_type pipelines (else return False)

    project = Project model instance .unique_name() property

    object_type = Lower cased ObjectType model .name property

    model = Classifier model (or Model) instance .name property

    index = Pipeline Number starting from 0 (Get that specific order classifier/model)
    """
    global data_val
    content = cache.get('classifier_cache', data_val)
    if project and object_type and content.get(project, False):
        if content.get(project).get(object_type, False):
            if index >= 0: # Search by index check if exists
                if len(content.get(project).get(object_type)) > index and content.get(project).get(object_type)[index]:
                    return content.get(project).get(object_type)[index]
            else: # search by model
                if model in content.get(project).get(object_type):
                    return model
    
    return False