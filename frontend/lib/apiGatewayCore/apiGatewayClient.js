/*
 * Copyright 2010-2016 Amazon.com, Inc. or its affiliates. All Rights Reserved.
 *
 * Licensed under the Apache License, Version 2.0 (the "License").
 * You may not use this file except in compliance with the License.
 * A copy of the License is located at
 *
 *  http://aws.amazon.com/apache2.0
 *
 * or in the "license" file accompanying this file. This file is distributed
 * on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
 * express or implied. See the License for the specific language governing
 * permissions and limitations under the License.
 */
 
var apiGateway = apiGateway || {};
apiGateway.core = apiGateway.core || {};

apiGateway.core.apiGatewayClientFactory = {};
apiGateway.core.apiGatewayClientFactory.newClient = function (simpleHttpClientConfig, sigV4ClientConfig) {
    var apiGatewayClient = { };
    //Spin up 2 httpClients, one for simple requests, one for SigV4
    var sigV4Client = apiGateway.core.sigV4ClientFactory.newClient(sigV4ClientConfig);
    var simpleHttpClient = apiGateway.core.simpleHttpClientFactory.newClient(simpleHttpClientConfig);

    apiGatewayClient.makeRequest = function (request, authType, additionalParams, apiKey) {
        //Default the request to use the simple http client
        var clientToUse = simpleHttpClient;
        var body;

        //Attach the apiKey to the headers request if one was provided
        if (apiKey !== undefined && apiKey !== '' && apiKey !== null) {
            request.headers['x-api-key'] = apiKey;
        }

        // --- PATCH: robust binary body detection (works across browsers/polyfills) ---
        if (
            (typeof Uint8Array !== 'undefined' && request.body instanceof Uint8Array) ||
            Object.prototype.toString.call(request.body) === "[object Uint8Array]"
        ) {
                // Uint8Array → send underlying ArrayBuffer
                body = request.body.buffer;
}
else if (
    request.body instanceof ArrayBuffer ||
    Object.prototype.toString.call(request.body) === "[object ArrayBuffer]"
) {
            // Raw ArrayBuffer
            body = request.body;
}
else if (
    typeof Blob !== "undefined" && request.body instanceof Blob
) {
            // File/Blob uploads (BEST for images)
            body = request.body;
}
else if (request.body === undefined || request.body === null) {
            body = undefined;
}
else {
            // JSON payload
            body = JSON.stringify(request.body);
        }

        // Ensure the request object contains the correct body to be sent by the underlying HTTP client
        request.body = body;


        // If the user specified any additional headers or query params that may not have been modeled
        // merge them into the appropriate request properties
        request.headers = apiGateway.core.utils.mergeInto(request.headers, additionalParams.headers);
        request.queryParams = apiGateway.core.utils.mergeInto(request.queryParams, additionalParams.queryParams);

        //If an auth type was specified inject the appropriate auth client
        if (authType === 'AWS_IAM') {
            clientToUse = sigV4Client;
        }

        //Call the selected http client to make the request, returning a promise once the request is sent
        return clientToUse.makeRequest(request);
    };
    return apiGatewayClient;
};
