(function(){
  const token = localStorage.getItem('obs_token');
  if (!token) { window.location.replace('login.html'); return; }
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    if (Date.now() / 1000 > payload.exp) {
      localStorage.removeItem('obs_token');
      window.location.replace('login.html');
    }
  } catch(e) {
    localStorage.removeItem('obs_token');
    window.location.replace('login.html');
  }
})();
