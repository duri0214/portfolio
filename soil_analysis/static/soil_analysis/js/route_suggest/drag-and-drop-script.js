$(document).ready(function () {
    $("#sortable-list").sortable();

    $("#orderForm").submit(function (event) {
        const order = $("#sortable-list").sortable("toArray");
        const filteredOrder = order.filter(item => item !== "");
        $("#orderData").val(filteredOrder.join(","));
    });
});
