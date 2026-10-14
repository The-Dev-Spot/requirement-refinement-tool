'use strict';
// Files are read only after a user selects them, then submitted as visible text.
document.querySelectorAll('[data-text-upload]').forEach(input => {
  input.addEventListener('change', async () => {
    const file = input.files[0];
    if (!file) return;
    const message = input.parentElement.querySelector('[role=status]');
    if (file.size > 100000) { message.textContent = 'Choose a UTF-8 text file smaller than 100 KB.'; input.value = ''; return; }
    try {
      const bytes = await file.arrayBuffer();
      const text = new TextDecoder('utf-8', {fatal: true}).decode(bytes);
      input.closest('form').querySelector('textarea[name=text]').value = text;
      message.textContent = 'Text loaded. Review it before saving.';
    } catch { message.textContent = 'This file could not be read as UTF-8 text.'; }
  });
});
