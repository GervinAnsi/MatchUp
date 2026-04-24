document.addEventListener("DOMContentLoaded", () => {
    const destructiveLinks = document.querySelectorAll("[data-confirm]");
    destructiveLinks.forEach(link => {
        link.addEventListener("click", (event) => {
            const text = link.getAttribute("data-confirm") || "Kas oled kindel?";
            if (!window.confirm(text)) {
                event.preventDefault();
            }
        });
    });
});
