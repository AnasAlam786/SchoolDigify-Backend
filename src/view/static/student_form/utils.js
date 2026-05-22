export function convertBlobToBase64(blob) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
}

export function showAlert(status, message) {
  if (typeof showAlert === 'function') {
    showAlert(status, message);
    return;
  }

  const alertText = `${status}: ${message}`;
  if (window.alert) {
    window.alert(alertText);
  } else {
    console.log(alertText);
  }
}

export function formatAadharNumber(input) {
  let value = input.value.replace(/\D/g, '');
  if (value.length <= 12) {
    value = value.replace(/(\d{4})(\d{1,4})/, '$1-$2');
    value = value.replace(/(\d{4})(\d{1,4})/, '$1-$2');
    value = value.replace(/(\d{4})(\d{1,4})$/, '$1-$2');
  }
  input.value = value;
}

export function attachDateMask(selector, format) {
  const el = document.querySelector(selector);
  if (!el) return;

  el.addEventListener('input', e => {
    let value = e.target.value;
    let numbers = value.replace(/\D/g, '').slice(0, 8);
    let newValue = '';

    if (format === 'DD-MM-YYYY') {
      if (numbers.length >= 5) {
        newValue = `${numbers.slice(0, 2)}-${numbers.slice(2, 4)}-${numbers.slice(4)}`;
      } else if (numbers.length >= 3) {
        newValue = `${numbers.slice(0, 2)}-${numbers.slice(2)}`;
      } else {
        newValue = numbers;
      }
    }

    if (newValue !== value) {
      e.target.value = newValue;
    }
  });
}

export function calculateAge(dobString) {
  const [day, month, year] = dobString.split('-').map(Number);
  const birthDate = new Date(year, month - 1, day);
  const today = new Date();
  let age = today.getFullYear() - birthDate.getFullYear();
  const monthDiff = today.getMonth() - birthDate.getMonth();

  if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
    age--;
  }

  return age;
}

export function getSuggestedClass(age) {
  if (age === 3) return 'Nursery or Pre-Nursery';
  if (age === 4) return 'Nursery';
  if (age === 5) return 'LKG';
  if (age === 6) return 'UKG';
  if (age === 7) return '1st';
  if (age === 8) return '2nd';
  if (age === 9) return '3rd';
  if (age === 10) return '4th';
  if (age === 11) return '5th';
  if (age === 12) return '6th';
  if (age === 13) return '7th';
  if (age === 14) return '8th';
  if (age === 15) return '9th';
  if (age === 16) return '10th';
  if (age === 17) return '11th';
  if (age > 17) return 'Above 12th';
  if (age < 3) return 'Too young for admission';
  return 'Age not suitable';
}
