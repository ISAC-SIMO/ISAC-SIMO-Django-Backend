# Important Notes:
---
+ [Creating Offline Models](#creating-offline-models)
+ [Classifier WITHOUT pre/post process](#classifier-without-pre-post-process)
+ [Classifier WITH pre/post process](#classifier-with-pre-post-process)
    * [Pre-Process](#pre-process)
    * [Post-Process](#post-process)
+ [Object Detect](#object-detect)
+ [URLs](#urls)

<div class="blink">

> **REMINDER:** In Offline Model the name of main function should always be ``run()``. Else, the pipeline will break/crash.

> **REMINDER:** To Create Pre/Post Process Offline Model, ``Processor`` Model Type should be selected. So, the Checkboxes are visible.

</div>

<div id="creating-offline-models"></div>

### Creating Offline Models:
**Attributes While CREATING:**

- Name = Offline Model Name (max length=200)
- Model Type = ``OBJECT DETECT`` or ``CLASSIFIER`` or ``PROCESSOR``
- Model Format = File Format of model (h5, py etc.)
- File = Upload File with format as provided
- Model Labels = Multiple labels with what this model will return (with proper index)
- Pre-Process = **Checkmark** this Offline Model as Pre-Process (e.g. Gaussian Blur to preprocess the image uploaded)
- Post-Process = **Checkmark** this Offline Model as Post-Process (e.g. Customize the pipeline result or go/nogo result)

> Type: **Object Detect** is linked in Projects & **Classifier** is linked while creating offline model classifiers.

> Type: **Processor** (.py Format) can be marked as **Pre-Process** or **Post-Process**. Note: If Model Type *Classifier* is Selected then it will only act as Classifier WITHOUT pre/post. The .py file should be made accordingly as shown below.
---
<div id="classifier-without-pre-post-process"></div>

### Classifier WITHOUT pre/post process:

The final output should always be in the format of 2-dimensional array ``[[0.650, 0.211]]`` *(For any Model Format)*

The array output will be linked to specific index of model labels provided. For example, if the labels provided are ``cat, dog`` then 0.650 will be cat and 0.211 will be dog.

---

In case of **python3 .py** model format make sure to name the main function ``run(pillow_instance, labels=[])`` which takes the pillow instance of image as first parameter and labels (can be empty) as 2nd parameter . It must return the 2-dimensional prediction output as stated above. Example:
```python
from cv2 import cv2
def run(img, labels=[]):
    # YOUR CODE.....
    return [[0.5,0.12]]
```
>*Make sure to get rid of all unnecessary codes like deleting the input files, saving temp. images, calling run() function etc.*
---

<div id="classifier-with-pre-post-process"></div>

### Classifier WITH pre/post process:
*Only applicable if .py format is selected*

<div id="pre-process"></div>

- ##### Pre-Process:
    - Usage Example: *Gussian Blur/Resize, Inverse, Canny image etc.*
    - Must have ``def run(img)`` as the main function where img is cv image instance
    - It must return a cv instance image
    - Process is terminated on crash
    - Example File:
    ```python
    from cv2 import cv2
    def run(img):
        gb1 = cv2.GaussianBlur(img, (5, 5), 1)
        gray = cv2.cvtColor(gb1,cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(gray,cv2.COLOR_BGR2GRAY)
        grayin = 255 - cv2.threshold(gray, 0,255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]

        width_percent = 224 / grayin.shape[1]
        height_percent = 224 / grayin.shape[0]

        width = int(grayin.shape[1] * width_percent)
        height = int(grayin.shape[0] * height_percent)
        dim = (width, height)
        resized = cv2.resize(grayin, dim, interpolation = cv2.INTER_AREA)

        return resized
    ```

<div id="post-process"></div>

- ##### Post-Process:
    - Usage Example: *Alter, Customize, Override: Status & Score*
    - Must have ``def run(img, pipeline_status, score, result)`` as the main function
    - ``img`` = cv instance of image
    - ``pipeline_status`` =
        - e.g. 
        ```
        {
            "Force Object Type": { # If Object Type ID Provided
                "score": "1",
                "result": "rebar shapes"
            },
            "pretest guss": { # Pre Processor will have the Offline Model Name
                "score": "1",
                "result": "Pre-Processed Success"
            },
            "rebarshapesclassifier_166863088": { # Other Classifier will have the Classifier Name
                "score": 0.92,
                "result": "Go"
            },
            "All Detected": [], # If Detect Model encountered, then all the detected Raw Output is stored
            "908b69dc-4b10-4e8a-be61-2469c99838f2": { # Detect Model OR Detect Model Acting as Classifier will have this
                "score": 0.5,
                "result": "u-hook"
            }
            "PostProcessor": { # Post Processor will have the Offline Model Name
                "score": "0.99999",
                "result": "go",
                "message": ["Ok","Success"]
            }
        }
        ```
    - ``score`` = Classifier Score of Image File after all pipeline before this (e.g. 0.5)
    - ``result`` = Classifier Result of Image File after all pipeline before this (e.g. go)
    - Process is terminated on crash only (Other Errors will return empty data)
    - It must return with this format:
        ```python
        return {
        'score': '0.9', # Score Given
        'result': 'go', # Result Name
        'message': '', # Can be string, or dictionary | Not Mandatory
        'break': True # Break and do not continue with other pipeline even if go/nogo | Not Mandatory
        }
        ```
    - Example File:
        ```python
        def run(img, pipeline_status, score, result):
            # Some codes to play with img, piepline etc.....
            # ...
            return {
                'score': '0.9',
                'result': 'go',
                'message': 'Processing Success',
                'break': False,
            }
        ```
---

<div id="object-detect"></div>

### Object Detect:
In case of ``OBJECT_DETECT`` the output can have multiple score along with multiple bounding box as below:
```python
    [
        [0.650, 0.211], # score (mapped to model labels e.g. wall, rebar)

        [
            {
                "left": 33,
                "top": 8,
                "width": 760,
                "height": 419
            }, # e.g. links to wall
            {
                "left": 80,
                "top": 10,
                "width": 200,
                "height": 100
            } # e.g. links to rebar
        ]
    ]
```
> Note: If Bounding is not provided then whole image will be used to classify.
> Note: Minimum Object Detect Score is 0.5 to continue
---

<div id="urls"></div>

### URLs:
> Offline Model Create: <a target="_blank" href="https://www.isac-simo.net/app/offline_model/create">https://www.isac-simo.net/app/offline_model/create</a>

> Classifier Create: <a target="_blank" href="https://www.isac-simo.net/app/watson/classifier/create">https://www.isac-simo.net/app/watson/classifier/create</a>, Choose **Just Add Classifier Without Training** and select the offline model if needed

<br/>
<center><small>ISAC-SIMO | IBM | Build Change</small></center>