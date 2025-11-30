// get api key from config file
const API_KEY = config.API_KEY;
const PHOTOS_BUCKET_ENDPOINT = "https://image-bucket-b2.s3.us-east-1.amazonaws.com/"; 

var apigClient = apigClientFactory.newClient({
    apiKey: API_KEY
});
document.getElementById('photoFile').addEventListener('change', function () {
    const file = this.files[0];
    const errorSpan = document.getElementById('fileError');

    if (!file) return;

    const allowedTypes = ["image/png", "image/jpg", "image/jpeg"];

    if (!allowedTypes.includes(file.type)) {
        errorSpan.innerText = "Unsupported file type. Allowed: PNG, JPG, JPEG.";
        this.value = ""; // clears the selected file
    } else {
        errorSpan.innerText = "";
    }
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
            const imageUrl = ref.url || `${PHOTOS_BUCKET_ENDPOINT}${ref.objectKey}`;

            const card = document.createElement('div');
            card.className = 'photo-card';
            const imgElement = document.createElement('img');
            imgElement.src = imageUrl;
            imgElement.alt = ref.objectKey;

            const meta = document.createElement('div');
            meta.className = 'meta';
            const key = document.createElement('div');
            key.className = 'key';
            key.textContent = ref.objectKey;
            const bucket = document.createElement('div');
            bucket.className = 'bucket';
            bucket.textContent = ref.bucket || '';
            const labels = document.createElement('div');
            labels.className = 'bucket muted';
            labels.textContent = (ref.labels && ref.labels.join(', ')) || '';

            meta.appendChild(key);
            meta.appendChild(bucket);
            if (labels && labels.textContent) meta.appendChild(labels);
            card.appendChild(imgElement);
            card.appendChild(meta);
            resultsGrid.appendChild(card);
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

// Hook up clear buttons and file preview behavior
const clearUploadBtn = document.getElementById('clearUpload');
if (clearUploadBtn) {
    clearUploadBtn.addEventListener('click', () => {
        document.getElementById('photoFile').value = '';
        document.getElementById('customLabels').value = '';
        const uploadMessage = document.getElementById('uploadMessage');
        if (uploadMessage) { uploadMessage.innerText = ''; uploadMessage.className = ''; }
        const previewEl = document.getElementById('uploadPreview');
        if (previewEl) { previewEl.style.display = 'none'; previewEl.src = ''; }
    });
}

const clearSearchBtn = document.getElementById('clearSearch');
if (clearSearchBtn) {
    clearSearchBtn.addEventListener('click', () => {
        document.getElementById('searchQuery').value = '';
        document.getElementById('resultsGrid').innerHTML = '';
    });
}

const photoFileInput = document.getElementById('photoFile');
if (photoFileInput) {
    photoFileInput.addEventListener('change', function(e) {
        const file = e.target.files[0];
        const previewEl = document.getElementById('uploadPreview');
        if (!file) { if (previewEl) { previewEl.style.display = 'none'; previewEl.src = ''; } return; }
        if (previewEl) { previewEl.src = URL.createObjectURL(file); previewEl.style.display = 'block'; }
    });
}
