// get api key from config file
const API_KEY = config.apiKey;
const PHOTOS_BUCKET_ENDPOINT = "https://image-bucket-b2.s3.us-east-1.amazonaws.com/"; 

var apigClient = apigClientFactory.newClient({
    apiKey: API_KEY
});

document.getElementById('searchForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    const query = document.getElementById('searchQuery').value;
    const resultsGrid = document.getElementById('resultsGrid');
    resultsGrid.innerHTML = 'Searching...';

    try {
        const params = {
            q: query
        };
        
        const additionalParams = {
        };

        const response = await apigClient.searchGet(params, additionalParams);

        const photoReferences = response.data; 
        const resultsGrid = document.getElementById('resultsGrid');
        resultsGrid.innerHTML = ''; 

        if (!photoReferences || photoReferences.length === 0) {
            resultsGrid.innerHTML = 'No photos found matching your query.';
            return;
        }

        const PHOTOS_BUCKET_ENDPOINT = "https://image-bucket-b2.s3.us-east-1.amazonaws.com/"; 

        photoReferences.forEach(ref => {

            const imageUrl = `${PHOTOS_BUCKET_ENDPOINT}${ref.objectKey}`;
            
            const imgElement = document.createElement('img');
            imgElement.src = imageUrl;
            imgElement.alt = ref.objectKey;
            resultsGrid.appendChild(imgElement);
        });
        console.log("Search response:", response);
        
    } catch (error) {
        console.error('Search failed:', error);
        resultsGrid.innerHTML = 'Error searching photos.';
    }
});

document.getElementById('uploadForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const fileInput = document.getElementById('photoFile');
    const customLabels = document.getElementById('customLabels').value;
    const uploadMessage = document.getElementById('uploadMessage');

    const file = fileInput.files[0];
    if (!file) {
        uploadMessage.innerText = 'Please select a file.';
        return;
    }

    const objectKey = file.name;
    // const cleanLabels = customLabels
    //     .split(',')
    //     .map(l => l.trim())
    //     .filter(l => l.length > 0)
    //     .join(', ');

    console.log("Custom Labels:", customLabels);
    console.log("custom label type", customLabels.type);

    const buffer = await file.arrayBuffer();
    const body = new Uint8Array(buffer);

    const params = {
        filename: objectKey, 
        "Content-Type": file.type || "image/jpeg",
        "x-amz-meta-customLabels": customLabels
    };

    const additionalParams = {
        headers: {
            "Content-Type": file.type || "image/jpeg",
            "x-amz-meta-customLabels": customLabels,
        }
    };

    try {
        const result = await apigClient.uploadPut(params, body, additionalParams);

        console.log("Upload result:", result);
        uploadMessage.innerText = "Photo Uploaded Successfully";
        document.getElementById('customLabels').value = "";

    } catch (err) {
        console.error("Upload error:", err);
        uploadMessage.innerText = "Photo Upload Failed: " + err.message;
    }
});
