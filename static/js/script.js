document.addEventListener("DOMContentLoaded", function () {

    const movementType = document.getElementById("movement_type");
    const adjustmentField = document.getElementById("adjustment_field");

    function updateAdjustmentField() {

        if (!movementType || !adjustmentField) {
            return;
        }

        if (movementType.value === "ADJUSTMENT") {
            adjustmentField.style.display = "block";
        } else {
            adjustmentField.style.display = "none";
        }
    }

    if (movementType) {
        movementType.addEventListener("change", updateAdjustmentField);
        updateAdjustmentField();
    }

});