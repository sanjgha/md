import "@testing-library/jest-dom";

// Create a root element for SolidJS rendering
if (!document.getElementById("root")) {
  const root = document.createElement("div");
  root.id = "root";
  document.body.appendChild(root);
}
