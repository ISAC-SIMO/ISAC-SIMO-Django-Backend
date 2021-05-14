# Integration with other Application
ISAC-SIMO API is a fully featured rest service which allows other applications to use the public api to add, edit and manage data and records externally. Learn more about the API provided by ISAC-SIMO in [Mobile Api Guide](/mobile-api-guide){target="_blank"}.

This examples below shows a demonstration on how we can easily integrate ISAC-SIMO into different applications specially the image testing:

## <span style="color:green">KoboToolbox</span>
KoboToolbox (kf.kobotoolbox.org) has a feature called **Rest Services** which allows us to integrate ISAC-SIMO with which it calls our API on each new submission added to the kobo form.

First, we need to make sure that the form contains **Photo** input with the data column name set to “isac_image_xxxx” where “xxxx” can be a unique identifier. The Form can contain multiple ISAC-SIMO test-able image upload fields with “xxxx” being unique for each field. If you want to receive back the ISAC-SIMO test result and store it in a field in the kobo submission record, a read-only text input field with data column name “isac_result_xxxx” can be created. The "xxxx" value must be the same as the image upload field.

Example we can have: "isac_image_1" as photo upload field and "isac_result_1" as the input field to store the result. When uploading, make sure that the isac_result_xxx field is not empty (e.g. add N/A as default value).

![](./assets/kobo/kobo-1.png)

Then, in the Kobo Rest Service we can then use the following endpoint.

![](./assets/kobo/kobo-2.png)

*https://www.isac-simo.net/api/kobo/?object_type_id=[check_id]&token=[kobo_token]&domain=[kobo_server_domain]*

The **object_type_id** value should be the ID of the chosen check (can be found in isac-simo dashboard). And, the **token** should be the Kobo Toolbox auth token that can be found in Account Settings of Kobo user dashboard. Domain used by ISAC-SIMO for sending back the result is `https://kc.kobotoolbox.org` by default. If you want to change the domain and use your custom server then provide a domain query parameter. The domain in the query parameter must NOT have ending slash.

The test result can be viewed in ISAC-SIMO Dashboard with description set to “KoboToolbox / ID”. You can search by _id value here.

![](./assets/kobo/kobo-3.png)

And, if “isac_result_xxxx” is valid then the result field will be set in kobo toolbox data also. It might take a few minutes for it to update / sync.

## <span style="color:green">Fulcrum</span>
Fulcrum is a popular Data Collection application that has a wide range of features. Integrating ISAC-SIMO into any Fulcrum project is pretty straight-forward. Most of the logic and standard are similar to that of the KoboToolbox method mentioned above.

First, we need to make sure that the form contains a **Photos** field with the data name set to “isac_image_xxxx” where “xxxx” can be a unique identifier. The photo field for faster performance should have a single maximum photo allowed. The Form can contain multiple ISAC-SIMO test-able photo upload fields with “xxxx” being unique for each field. If you want to receive back the ISAC-SIMO test result and store it in a field in fulcrum record, a read-only or hidden **text** input field with data name “isac_result_xxxx” can be created. The "xxxx" value must be the same as the image upload field.

Example we can have: "isac_image_1" as photo upload field and "isac_result_1" as the input field to store the result.

![](./assets/fulcrum/fulcrum-1.png)

Fulcrum has a feature called "Webhook", with which on any event like; create, edit etc. fulcrum can call ISAC-SIMO API with form data. ISAC-SIMO performs tests on photos if valid data names are provided and updates the record if valid data name for result field is provided.

![](./assets/fulcrum/fulcrum-2.png)

*https://www.isac-simo.net/api/fulcrum/?object_type_id=[check_id]&token=[kobo_token]*

The **object_type_id** value should be the ID of the chosen check (can be found in isac-simo dashboard). And, the **token** should be the Fulcrums API token that can be found in the Settings / API section of the dashboard.

The test result can be viewed in ISAC-SIMO Dashboard with description set to Fulcrum / ID”. You can search by id value here. Any recurring webhooks with the same ID are ignored by rate-limiting.

![](./assets/fulcrum/fulcrum-3.png)

If “isac_result_xxxx” is valid then the result field will be set in fulcrum data also. It might take a few minutes for it to update / sync.

![](./assets/fulcrum/fulcrum-4.png)

<hr/>

Any other services can easily integrate ISAC-SIMO using our Restful API service. [Learn More](/mobile-api-guide){target="_blank"}.