document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('qr-form');
  const urlInput = document.getElementById('url-input');
  const generateBtn = document.getElementById('generate-btn');
  const clearBtn = document.getElementById('clear-btn');
  const pasteBtn = document.getElementById('paste-btn');
  const exampleChips = document.querySelectorAll('.example-chip');
  
  const errorAlert = document.getElementById('error-alert');
  const errorMessage = document.getElementById('error-message');
  
  const resultContainer = document.getElementById('result-container');
  const qrImage = document.getElementById('qr-image');
  const encodedUrlEl = document.getElementById('encoded-url');
  const copyUrlBtn = document.getElementById('copy-url-btn');
  const downloadBtn = document.getElementById('download-btn');
  const openLinkBtn = document.getElementById('open-link-btn');
  const toast = document.getElementById('toast');

  let currentEncodedUrl = '';
  let toastTimeout = null;

  // Show toast notification
  function showToast(message) {
    if (toastTimeout) clearTimeout(toastTimeout);
    toast.textContent = message;
    toast.classList.add('show');
    toastTimeout = setTimeout(() => {
      toast.classList.remove('show');
    }, 2500);
  }

  // Display error alert
  function showError(msg) {
    errorMessage.textContent = msg;
    errorAlert.style.display = 'flex';
    resultContainer.style.display = 'none';
  }

  // Hide error alert
  function hideError() {
    errorAlert.style.display = 'none';
    errorMessage.textContent = '';
  }

  // Set loading state
  function setLoading(isLoading) {
    if (isLoading) {
      generateBtn.classList.add('loading');
      generateBtn.disabled = true;
    } else {
      generateBtn.classList.remove('loading');
      generateBtn.disabled = false;
    }
  }

  // Reset/Clear generator
  function clearAll() {
    urlInput.value = '';
    hideError();
    resultContainer.style.display = 'none';
    currentEncodedUrl = '';
    urlInput.focus();
  }

  // Client-side quick check
  function validateClientUrl(rawUrl) {
    const url = rawUrl.trim();
    if (!url) {
      return { valid: false, message: 'Please enter a website URL.' };
    }
    if (!/^https?:\/\//i.test(url)) {
      return { 
        valid: false, 
        message: 'Please include the protocol: http:// or https:// (e.g., https://example.com)' 
      };
    }
    return { valid: true, url };
  }

  // Submit and generate QR code
  async function generateQRCode(urlToEncode) {
    const check = validateClientUrl(urlToEncode);
    if (!check.valid) {
      showError(check.message);
      return;
    }

    hideError();
    setLoading(true);

    try {
      const response = await fetch('/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'application/json'
        },
        body: JSON.stringify({ url: check.url })
      });

      const data = await response.json();

      if (!response.ok || !data.success) {
        showError(data.error || 'Failed to generate QR code.');
        return;
      }

      // Success: render QR and metadata
      currentEncodedUrl = data.url;
      qrImage.src = data.qr_image;
      encodedUrlEl.textContent = data.url;
      encodedUrlEl.title = data.url;

      // Configure download button
      downloadBtn.href = data.qr_image;
      downloadBtn.download = data.filename || 'qrcode.png';

      // Show result section
      resultContainer.style.display = 'block';
      resultContainer.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

    } catch (err) {
      showError('Network error or server unavailable. Please try again.');
      console.error('QR Generation error:', err);
    } finally {
      setLoading(false);
    }
  }

  // Form submit handler
  form.addEventListener('submit', (e) => {
    e.preventDefault();
    generateQRCode(urlInput.value);
  });

  // Clear button handler
  clearBtn.addEventListener('click', clearAll);

  // Paste button handler
  pasteBtn.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          urlInput.value = text.trim();
          hideError();
          urlInput.focus();
          showToast('URL pasted from clipboard');
        }
      } else {
        urlInput.focus();
      }
    } catch {
      urlInput.focus();
    }
  });

  // Example chips click
  exampleChips.forEach(chip => {
    chip.addEventListener('click', () => {
      const sample = chip.getAttribute('data-sample');
      if (sample) {
        urlInput.value = sample;
        hideError();
        generateQRCode(sample);
      }
    });
  });

  // Copy encoded URL button
  copyUrlBtn.addEventListener('click', async () => {
    if (!currentEncodedUrl) return;
    try {
      await navigator.clipboard.writeText(currentEncodedUrl);
      const copyText = copyUrlBtn.querySelector('.copy-text');
      const originalText = copyText.textContent;
      copyText.textContent = 'Copied!';
      showToast('Encoded URL copied to clipboard!');
      setTimeout(() => {
        copyText.textContent = originalText;
      }, 2000);
    } catch (err) {
      showToast('Could not copy to clipboard.');
    }
  });

  // Open / Test Link button
  openLinkBtn.addEventListener('click', () => {
    if (currentEncodedUrl) {
      window.open(currentEncodedUrl, '_blank', 'noopener,noreferrer');
    }
  });
});
