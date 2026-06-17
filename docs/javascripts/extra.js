// Make the site title in the header clickable (navigates home like the logo).
// Material for MkDocs uses two .md-header__topic elements:
//   [0] = site name (always visible at top, hidden on scroll)
//   [1] = page/section title (shown on scroll)
// Only the site name should link home.
document.addEventListener("DOMContentLoaded", function () {
  var topics = document.querySelectorAll(".md-header__topic");
  var logo = document.querySelector(".md-header__button.md-logo");
  if (topics.length > 0 && logo) {
    topics[0].style.cursor = "pointer";
    topics[0].addEventListener("click", function () {
      window.location.href = logo.href;
    });
  }
});
