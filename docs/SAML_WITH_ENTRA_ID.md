# SAML with Microsoft Entra ID

This is a reference guide for integrating with Microsoft Entra ID (formerly Azure Active Directory) and SAML. Please modify the detailed parameters to suit your environment.

## Prerequisites

We will perform the initial deployment of this solution. After the initial deployment, we will integrate Cognito with Entra ID using SAML.

From the Output tab, note down the Cognito User Pool ID and Cognito Domain Name.

![image-20240722224831](assets/SAML_WITH_ENTRA_ID/image-20240722224831.png)


## Setting up Microsoft Entra ID

Enable SAML integration with Microsoft Entra ID (formerly Azure Active Directory).

Open the Microsoft Entra ID configuration screen from Microsoft Azure.

![image-202407222213133](assets/SAML_WITH_ENTRA_ID/image-20240722221313.png)

Select *Enterprise Applications*.

![image-202407222215057](assets/SAML_WITH_ENTRA_ID/image-20240722221505.png)

Select *New application*.

![image-202407222215555](assets/SAML_WITH_ENTRA_ID/image-20240722221555.png)

Select *Create your own application*

![image-202407222216295](assets/SAML_WITH_ENTRA_ID/image-20240722221629.png)

Enter any application name and click Create. In this example, we use 'ComfyUI'.

![image-20240722214943](assets/SAML_WITH_ENTRA_ID/image-20240722214943.png)

From the Single sign-on menu, select *SAML*.

![image-20240722215042](assets/SAML_WITH_ENTRA_ID/image-20240722215042.png)

Click *Edit* in Basic SAML Configuration.

![image-20240722215122](assets/SAML_WITH_ENTRA_ID/image-20240722215122.png)

Enter the following parameters and click Save. Use the Cognito user pool ID and Cognito Domain Name you confirmed in [Prerequisites](#Prerequisites).

Identifier (Entity ID) 

```
# Format
urn:amazon:cognito:sp:<UserPoolID>

# Example
urn:amazon:cognito:sp:us-west-2_oHbx7m6Wo
```

Reply URL (Assertion Consumer Service URL)

```
# Format
https://<cognito domain name>.auth.yourRegion.amazoncognito.com/saml2/idpresponse

# Example
https://your-preferred-name.auth.ap-northeast-1.amazoncognito.com/saml2/idpresponse
```

Specify a value and click Save.

![image-20240722215256](assets/SAML_WITH_ENTRA_ID/image-20240722215256.png)

The settings have been applied.

![image-20240722215437](assets/SAML_WITH_ENTRA_ID/image-20240722215437.png)

Select *Download* for Federation Metadata XML to obtain the XML file.

![image-20240722215551](assets/SAML_WITH_ENTRA_ID/image-20240722215551.png)

Add users or groups to associate with this application. Only the associated users or groups can log in here.

![image-20240722215632](assets/SAML_WITH_ENTRA_ID/image-20240722215632.png)

In this example, we specify a user that was created in advance. Please specify according to your environment.

![image-20240722215712](assets/SAML_WITH_ENTRA_ID/image-20240722215712.png)

Click Assign.

![image-20240722220121](assets/SAML_WITH_ENTRA_ID/image-20240722220121.png)

## Cognito Configuration: Federation

Return to the Cognito  in the AWS Management Console.
Open the Cognito User Pool screen, and from the Sign-in experience tab, select Add identity provider.

![image-202407222244517](assets/SAML_WITH_ENTRA_ID/image-20240722224451.png)

To use SAML for integration with Entra ID, select SAML.

![image-202407222245295](assets/SAML_WITH_ENTRA_ID/image-20240722224529.png)

Enter any easily identifiable name for Provider name.
Select Choose file and upload the "Federation Metadata XML" downloaded from Entra ID.

![image-20240722222618](assets/SAML_WITH_ENTRA_ID/image-20240722222618.png)

For the User pool attribute, specify email, surname and givenname.
For the SAML attribute, select the following string and choose Add identity provider:

```
http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress
http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname
http://schemas.xmlsoap.org/ws/2005/05/identity/claims/surname
```

![image-20240722222631](assets/SAML_WITH_ENTRA_ID/image-20240722222631.png)

A new setting has been added.

![image-202407222250538](assets/SAML_WITH_ENTRA_ID/image-202407222250538.png)

## Configuring Cognito: Hosted UI

We will configure the settings to use the added Entra ID integration with the Hosted UI. Select the App Integration tab.

![image-20240722220121](assets/SAML_WITH_ENTRA_ID/image-20240722220121.png)

Specify an existing App Client.

![image-20240722220133](assets/SAML_WITH_ENTRA_ID/image-20240722220133.png)

Press Edit.

![image-20240722220154](assets/SAML_WITH_ENTRA_ID/image-20240722220154.png)

Select EntraID as the Identity Provider. Also, uncheck the Cognito user pool checkbox as you want to stop authentication using the Cognito user pool.

![image-20240722220307](assets/SAML_WITH_ENTRA_ID/image-20240722220307.png)

Select Save changes.

## Editing cdk.json

Since the configuration is now complete, we will change the values in cdk.json.

- samlAuthEnabled: Set to `true`. This will switch to the SAML-only authentication screen, and the conventional authentication function using Cognito user pools will no longer be available.

```json
  "context": {
　　 ...
    "samlAuthEnabled": true,
```

After configuration, redeploying will enable SAML integration.
