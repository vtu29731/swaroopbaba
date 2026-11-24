document.addEventListener("DOMContentLoaded", () => {
  const menuToggle = document.querySelector(".menu-toggle");
  const navLinks = document.querySelector(".nav-links");
  if (menuToggle && navLinks) {
    menuToggle.addEventListener("click", () => {
      const open = navLinks.classList.toggle("is-open");
      menuToggle.setAttribute("aria-expanded", String(open));
      menuToggle.setAttribute("aria-label", open ? "Close navigation" : "Toggle navigation");
    });
  }

  document.querySelectorAll(".flash-close").forEach((button) => {
    button.addEventListener("click", () => button.parentElement.remove());
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });

  const registerForm = document.querySelector("#register-form");
  if (registerForm) {
    const password = registerForm.querySelector("#password");
    const confirmPassword = registerForm.querySelector("#confirm-password");
    const validate = () => {
      confirmPassword.setCustomValidity(
        confirmPassword.value && confirmPassword.value !== password.value
          ? "Passwords do not match."
          : ""
      );
    };
    password.addEventListener("input", validate);
    confirmPassword.addEventListener("input", validate);
  }
});
