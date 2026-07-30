// used in src/view/static/student.js
// used in src/view/static/promote_students.js

async function sendMessage(studentId) {
    try {
      const resp = await fetch(`/api/create_watsapp_message_api?student_id=${encodeURIComponent(studentId)}`);
      const data = await resp.json();
      if (resp.ok) {
        sendWhatsAppMessage(data.phone, data.watsapp_message);
      } else {
        this.showAlert(resp.status, data.message);
      }
    } catch (err) {
      console.error('Error sending message:', err);
    }
  }

function sendWhatsAppMessage(phone, message) {
    // 1. Convert and validate phone
    try {
        phone = phone.toString().trim();
    } catch (e) {
        showAlert(400, "📞 Invalid phone number format.");
        return;
    }

    // 2. Remove all non-digit characters
    let formattedPhone = phone.replace(/\D/g, '');

    // 3. Handle common error cases
    if (formattedPhone.startsWith('0')) {
        formattedPhone = formattedPhone.substring(1); // remove leading 0
    }

    if (formattedPhone.length !== 10) {
        showAlert(400, "📞 Invalid phone number. It must be 10 digits.");
        return;
    }

    // 4. Add country code
    formattedPhone = '91' + formattedPhone;

    // --- Global rate limiting ---
    const storageKey = 'wa_global_limit';
    const now = Date.now();
    const today = new Date().toISOString().slice(0, 10); // YYYY-MM-DD
    const data = JSON.parse(localStorage.getItem(storageKey) || '{"lastSent":0,"count":0,"date":""}');

    // Reset daily count if new day
    if (data.date !== today) {
        data.count = 0;
        data.date = today;
    }

    // Random delay between 10 and 15 seconds (10000–15000  ms)
    const randomDelay = Math.floor(Math.random() * 5000) + 10000;

    if (now - data.lastSent < randomDelay) {
        showAlert(400, `⏱ Please wait ${Math.ceil((randomDelay - (now - data.lastSent))/1000)} seconds before sending another message.`);
        return;
    }

    // Daily limit check
    if (data.count >= 200) {
        showAlert(400, "📵 Daily limit of 200 messages reached.");
        return;
    }

    // ---------- OPEN WHATSAPP ----------

    // 5. Encode the message
    const encodedMessage = encodeURIComponent(message || '');

    // 6. Check if device is mobile or desktop
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

    if (isMobile) {
        // Open WhatsApp on mobile
        window.location.href = `whatsapp://send?phone=${formattedPhone}&text=${encodedMessage}`;
    } else {
        // Open WhatsApp Web on desktop
        window.open(
            `https://web.whatsapp.com/send?phone=${formattedPhone}&text=${encodedMessage}`,
            '_blank'
        );
    }

    // ---------- UPDATE LIMITS ----------
    data.lastSent = now;
    data.count += 1;
    localStorage.setItem(storageKey, JSON.stringify(data));
}
