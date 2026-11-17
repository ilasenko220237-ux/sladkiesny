// Маски ввода (только удобство; проверка данных выполняется на сервере)
$(document).ready(function () {
    $('#phone').inputmask({"mask": "+7(999)999-99-99"});
    $('#check_in, #check_out').inputmask({"mask": "99.99.9999"});
});
