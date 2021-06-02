# Call to Action for Developers
We would like to invite developers and other interested folks to contribute to further development of this project and help make ISAC-SIMO a robust tool with a wide catalog of quality checks accessible by homeowners, builders, and local authorities to enable safe construction practices in areas with lack of technical support. The potential areas for further developments are listed below.

## Short term updates:

- **User interface improvements:**
    - Suggest improvements to the UI of the mobile app to make the process as intuitive and user-friendly for non-technical users.
    - Suggest improvements or new features to the dashboard to enable a wider use of the platform and cater to different users like developers, project managers, general users etc.

- **Crowdsource image dataset for ML training:**
    - Contribute image dataset for different construction elements (eg. walls and type of walls, openings, rebar cages, rebar stirrups etc.) that can be used to train object detection or segmentation models to detect and extract key construction elements from a construction site image. To contribute image dataset of construction elements, both ISAC-SIMO mobile app or the dashboard can be used by [following these guidelines](https://www.isac-simo.net/docs/web-application/#crowdsource-image).

- **Auto-perspective fix of wall / facade images:**
    - Support to automatically detect a skewed perspective in an image, and automatically fix the perspective of the image to front perspective. To detect the perspective, the segmentation mask obtained after passing the raw image through the unet model can be used instead of the raw image to make it easier to detect a skewed perspective in an image.

    ![](./assets/contribute/perspective-raw.png "Perspective Raw" )
    *Figure :*

    *Top row - Images that need a perspective fix*

    *Bottom row - Images that don’t need a perspective fix*

    ---

    ![](./assets/contribute/perspective-processed.png "Perspective Processed" )
    *Figure : Segmentation mask obtained from trained Unet model*

    *Top row - Images needing perspective fix*

    *Bottom row - Images that don’t need perspective fix*

    **To download these images for trial, [click here](./assets/contribute/perspective-raw.zip).**


## Long term updates:
In the long term, we envision ISAC-SIMO to contain a wide catalogue of checks that can be deployed in multiple contexts around the world to help bridge the gap in technical support to homeowners, builders, and local authorities to assist with the construction of disaster resilient confined masonry houses. To create a seamless experience for the users, we would need to be able to detect key construction elements from photos of construction sites taken at different stages of construction, and assess the detected elements for compliance or non-compliance. 

In order to achieve that, we would need to:

**1)** train a wide variety of models that can identify and extract key construction elements from construction site images, and

**2)** classify or process the images to assess the quality of the identified construction element as per the recommended guideline.

We would like to invite interested developers and other supporters of this project to contribute to the development of more quality checks in the long term with the following activities:

  - Crowd-source image dataset to train new models and create new checks
  - Train object detection models to identify key construction components from construction site images
  - Train new machine learning models or contribute python scripts to help extract key features in the images of construction elements and assess their quality as per the recommended guidelines

To implement the checks, we can use a combination of machine learning models (such as object detection, segmentation, classification models) along with python scripts to carry out image processing and compute the final result of an assessment. 

We can thereby implement a three-step pipeline in the backend for each check:

1) **Object Detection:** Implement an object detection model to detect the construction element of interest from an image of a construction site.

2) **Pre-processing:** Implement a pre-processing python script to extract the bounding box corresponding to the detected construction element and pre-process the image using a pre-trained deep learning model or image processing functions, as appropriate for the check.

3) **Post-processing:** Implement a post-processing python script to analyze the segmentation mask or the processed image to extract key features and compute compliance or non-compliance as per the check requirements using machine learning models or python.

The list of construction elements to be detected and the catalogue of quality checks that can be implemented for confined masonry houses are detailed in the next section.

### Object Detection
Given enough image dataset, we can train and deploy object detection models to identify key construction elements from construction site images. The key components of a confined masonry construction is shown in the figure below.

![](./assets/contribute/masonry-building-detail.png "Masonry Building" )
*Figure: Key components and characteristics of a confined masonry building (Schacher 2015)*

Out of the confined masonry building components, we can train object detection models to identify the elements listed in the table below.

<table id="contribute-quality-checks">
    <tr>
      <th>#</th>
      <th>Element to be detected</th>
      <th>Example(s)</th>
      <th>Description</th>
    </tr>
    <tr>
      <td>1</td>
      <td><b>Facade</b></td>
      <td>
        <img src="../assets/contribute/facade.png" alt="Facade"/><br/>
        <img src="../assets/contribute/facade-alt.png" alt="Facade Alt"/>
      </td>
      <td>Detect a facade of a building</td>
    </tr>
    <tr>
      <td>2</td>
      <td><b>Storeys</b></td>
      <td>
        <img src="../assets/contribute/storeys.jpg" alt="Storeys"/>
      </td>
      <td>Detect multiple storeys in a facade of a building</td>
    </tr>
    <tr>
      <td>3</td>
      <td><b>Openings</b></td>
      <td>
        <img src="../assets/contribute/openings.jpg" alt="Openings"/><br/>
        <img src="../assets/contribute/openings-alt.jpg" alt="Openings Alt"/>
      </td>
      <td>Detect openings and their position</td>
    </tr>
    <tr>
      <td>4</td>
      <td><b>Masonry Walls</b></td>
      <td>
        <img src="../assets/contribute/masonry.jpg" alt="Masonry Walls"/><br/>
        <img src="../assets/contribute/masonry-alt.png" alt="Masonry Walls Alt"/>
      </td>
      <td>Detect full solid wall panels</td>
    </tr>
    <tr>
      <td>5</td>
      <td><b>Confining Concrete Elements</b></td>
      <td>
        <img src="../assets/contribute/confining-concrete-elements.jpg" alt="Confining Concrete Elements"/><br/>
        <img src="../assets/contribute/confining-concrete-elements-alt.png" alt="Confining Concrete Elements Alt"/><br/>
        Naming of horizontal and vertical ties
      </td>
      <td>Detect confining elements such as tie beams and tie columns</td>
    </tr>
    <tr>
      <td>6</td>
      <td><b>Rebar Elements</b></td>
      <td>
        <img src="../assets/contribute/rebar-elements.png" alt="Rebar Elements"/>
      </td>
      <td>
        Detect rebar elements such as rebar cage, rebar stirrup, longitudinal rebars, and seismic bands and obtain segmentation masks for rebar cages. 
        <br/><br/>
        Note: It may not be necessary to create separate colored masks for horizontal and vertical rebar elements as shown in the example and might suffice to represent all rebar with the same color.
      </td>
    </tr>
</table>
*Table 1: Key construction elements that can be detected for further assessment of confined masonry building*

### Quality Checks
  After detecting the key construction elements, we can extract the region corresponding to the element detected along with the position of the element in the original image for further analysis of compliance. Depending on the need of each quality check, we can either process the image to extract key features using python scripts to compute the compliance, or deploy additional machine learning models to detect key features before determining the final result. 

  The catalogue of checks that can be developed for a variety of confined masonry house typologies are listed in the table below. Although in reality there are more checks that can be developed for confined masonry houses, a lot of the checks depend on the capability to extract accurate measurements to determine the compliance. So the following list outlines the checks that can be performed using relative comparisons without necessarily getting the exact measurements. 

  <table id="contribute-quality-checks">
    <tr>
      <th>#</th>
      <th>Check</th>
      <th>Example</th>
      <th>Description & Applicability</th>
    </tr>
    <tr>
      <td>1</td>
      <td><b>Masonry unit type</b></td>
      <td>
        <img src="../assets/contribute/image-009.png" alt="Bricks"/><br/>
        (Hollow clay block, Hollow concrete block, solid clay block, solid concrete block, perforated clay block, etc.)
      </td>
      <td>Detect the type of masonry unit used for construction. Although a variety of masonry units are used in the construction of confined masonry buildings, the type of block used determines the overall strength of the masonry walls and thereby have different requirement for compliance</td>
    </tr>

    <tr>
      <td>2</td>
      <td><b>Percentage of holes in hollow blocks</b></td>
      <td>
        <img src="../assets/contribute/image-010.png" alt="Hollow Blocks"/>
        <img src="../assets/contribute/image-011.png" alt="Hollow Blocks"/>
      </td>
      <td>For hollow or perforated masonry units, check for ratio of holes to horizontal surface</td>
    </tr>

    <tr>
      <td>3</td>
      <td><b>Type of Masonry Wall</b></td>
      <td>
        <img src="../assets/contribute/block-wall.png" alt="Concrete Block Wall & Clay Block Wall"/><br/>
        <img src="../assets/contribute/plastered-wall.png" alt="Plastered Wall"/>
      </td>
      <td>Classify the type of wall. Eg: Plastered wall, concrete block wall, clay block wall etc.</td>
    </tr>

    <tr>
      <td>4</td>
      <td><b>Bond pattern check for concrete blocks</b></td>
      <td>
        <img src="../assets/contribute/image-012.png" alt="Bond Pattern"/><br/>
        <img src="../assets/contribute/bond-pattern.png" alt="Bond Pattern Alt"/>
      </td>
      <td>A quality check to assess the bond pattern in concrete block walls. 
      <br/><br/>
      Note: This check has been created so far for the clay block walls by using a combination of segmentation step using unet model followed by image processing of the mask image. A similar approach can be used for the concrete block wall, but we would need a different model to detect the mortar regions in the image.
      </td>
    </tr>

    <tr>
      <td>5</td>
      <td><b>Mortar thickness check for concrete blocks</b></td>
      <td>
        <img src="../assets/contribute/mortar-thickness.png" alt="Mortar thickness"/>
      </td>
      <td>A quality check to assess the mortar thickness in concrete block walls</td>
    </tr>

    <tr>
      <td>6</td>
      <td><b>Wall thickness</b></td>
      <td>
        <img src="../assets/contribute/image-013.png" alt="Wall thickness"/>
      </td>
      <td>A quality check to compare the thickness of the wall to the total height of the wall.
      <br/><br/>
      Note: The exact requirement for the ratio of wall thickness to height may vary depending on the type of block used to build the wall
      </td>
    </tr>

    <tr>
      <td>7</td>
      <td><b>Toothing in wall column intersections</b></td>
      <td>
        <img src="../assets/contribute/image-017.png" alt="Toothing in wall column intersections"/><br/>
        <img src="../assets/contribute/toothing-in-wall-column.png" alt="Toothing in wall column intersections Alt"/>
      </td>
      <td>Detect if toothing is present at the wall column intersections, and if so, determine if it’s less than ½ of brick length</td>
    </tr>

    <tr>
      <td>8</td>
      <td><b>Opening Size</b></td>
      <td>
        <img src="../assets/contribute/opening-size.png" alt="Opening Size"/>
      </td>
      <td>After detecting walls with openings, calculate the relative width of the opening with the length of the wall panel</td>
    </tr>

    <tr>
      <td>9</td>
      <td><b>Detect shear walls on each facade (wall panels without openings that are confined)</b></td>
      <td>
        <img src="../assets/contribute/shear-walls.png" alt="Shear walls"/>
      </td>
      <td>Detect if the facade has at least one wall panel that is confined with tie columns</td>
    </tr>
    
    <tr>
      <td>10</td>
      <td><b>Vertical continuity of openings (in case of multi-storey house)</b></td>
      <td>
        <img src="../assets/contribute/image-014.png" alt="Vertical continuity - Yes"/>
        <img src="../assets/contribute/image-015.png" alt="Vertical continuity - No"/>
      </td>
      <td>Check for continuity of openings in multi-storey buildings.</td>
    </tr>

    <tr>
      <td>11</td>
      <td><b>Presence or absence of confining elements around openings</b></td>
      <td>
        <img src="../assets/contribute/presence-of-confining-elements.png" alt="Opening Size"/><br/>
        Openings with confinement
      </td>
      <td>Detect presence of confining elements around openings</td>
    </tr>

    <tr>
      <td>12</td>
      <td><b>Rebar Cage Quality and Stirrup Spacing</b></td>
      <td>
        <img src="../assets/contribute/rebar-cage.png" alt="Rebar Cage"/><br/>
        Actual rebar cage requirements
      </td>
      <td>
        Detect poor quality reused rebar by identifying features such as bent longitudinal rebars, rebar cages with rebar stirrups that are too far apart.
        <br/><br/>
        We can compute the no. of rebar ties  relative to the height of the longitudinal rebar, and the spacing between rebar ties with the help of their position, in order to approximately assess if the stirrups are too far apart. 
        <br/><br/>
        Note: In order to carry out this analysis, we might need to first obtain a segmentation mask of horizontal and vertical rebar elements
        <br/><br/>
        <img src="../assets/contribute/rebar-cage-alt.png" alt="Parameters for approximate assessment"/><br/>
        Parameters for approximate assessment
      </td>
    </tr>
  </table>

  *Note: This is not a comprehensive list of checks but includes checks that can be done visually.*

  *Table 2: Quality checks that can be developed for confined masonry buildings*

---

### Mobile App Updates
**Additional functionalities that could enhance the performance and improve applicability of the tool in future implementations.**

- Support for streaming and video processing
- Implement AR for providing estimated measurements
- **Add more features in the mobile app:**
    - Offline functionality
    - Third Party Integration
    - Multiple language support
    - Auto-object detection of construction elements
        - Detects Objects when capturing images without having to choose the check type manually.
    - Real time object detection when capturing picture
        - Detects all objects (wall, rebar, brick etc.) in the camera screen in real-time and shows squares around them. And Be able to toggle on/off.
    - Quality Check via Video Recording
        - Support the Quality Check to be performed by recording video of the construction site. Instead of only Photos, we can also allow recording videos. The Back-end API exists but might need optimization.
    - Store and Review previous test results
        - For Guest as well as Logged in users, add a feature to store previous tests performed in that device to review later. Currently we only see once.

### Web Platform Updates
  - More Model Format Support:
      - Currently ISAC-SIMO supports h5, hdf5, keras and standard python3 scripts. It can be upgraded to support Pickled Python (pkl), Petastorm, Protobuf (pb), Apple ML Model (mlmodel), Torch Script (pt) and other popular machine learning file stores and formats.
  - Support Multiple Image URLs:
      - When testing photos against checks, users can either upload multiple image files or provide image url (currently only single). We can add features to support multiple image urls and store them in a single row instead of having a single image url per row in test result. As we have to fetch multiple images from multiple image urls, it might cause an asynchronous problem.
  - Edit Python3 Scripts / Offline Model directly from Web Application:
      - Everytime we need to make some changes to our python3 scripts, pre & post processor we have to edit the offline model and upload a new file every single time. We can have a feature to securely edit Python Scripts directly from the web application and immediately apply the changes.
  - Rate Limiting Per Action:
      - Currently, rate limiting can be handled by web servers (Nginx, Apache). We can have a feature to rate limit users based on logged-in user ID or IP Address in our application. The Rate Limit can be applied separately for separate features / modules. For Example, we can rate limit crowdsource upload per minute, but keep the rate-limit separately for other parts of the application.
  - Captcha Integration:
      - We can integrate Captcha for different actions within our web and mobile applications. We can add captcha verification for registration, running image tests, crowdsource upload, contribution submission etc.
