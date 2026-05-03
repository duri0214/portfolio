function initLandLedgerCreateModal(urls, folderName) {
    const modal = document.getElementById('landLedgerCreateModal');
    const form = document.getElementById('landLedgerCreateForm');
    const loadingDiv = document.getElementById('modalLoading');
    const btnSubmit = document.getElementById('btnSubmitLedger');
    const errorDiv = document.getElementById('formErrors');
    const errorMessages = document.getElementById('errorMessages');

    if (!modal) return;

    // モーダル表示時にフォームデータを読み込み
    modal.addEventListener('show.bs.modal', function () {
        loadFormData();
    });

    // フォーム送信処理
    form.addEventListener('submit', function (e) {
        e.preventDefault();
        submitForm();
    });

    function loadFormData() {
        // ローディング表示
        loadingDiv.style.display = 'block';
        form.style.display = 'none';
        errorDiv.style.display = 'none';

        // フォルダ名を表示
        document.getElementById('folderNameDisplay').textContent = folderName;

        // Ajax でフォームデータを取得
        fetch(`${urls.land_ledger_create_ajax}?folder_name=${encodeURIComponent(folderName)}`)
            .then(response => response.json())
            .then(data => {
                // 各セレクトボックスにオプションを設定
                populateSelect('id_land', data.lands, 'id', 'name', 'selected');
                populateSelect('id_crop', data.crops, 'id', 'name');
                populateSelect('id_land_period', data.land_periods, 'id', 'name');
                populateSelect('id_sampling_method', data.sampling_methods, 'id', 'name', 'selected');
                populateSelect('id_analytical_agency', data.analytical_agencies, 'id', 'name');
                populateSelect('id_sampling_staff', data.sampling_staff, 'id', 'name');

                // 採土日を設定
                const samplingDateInput = document.getElementById('id_sampling_date');
                if (data.suggested_sampling_date) {
                    samplingDateInput.value = data.suggested_sampling_date;
                } else {
                    const today = new Date();
                    const todayStr = today.getFullYear() + '-' +
                        String(today.getMonth() + 1).padStart(2, '0') + '-' +
                        String(today.getDate()).padStart(2, '0');
                    samplingDateInput.value = todayStr;
                }

                // フォーム表示
                loadingDiv.style.display = 'none';
                form.style.display = 'block';
            })
            .catch(error => {
                console.error('Error loading form data:', error);
                showError('フォームデータの読み込みに失敗しました。');
                loadingDiv.style.display = 'none';
            });
    }

    // データを保持する
    let allLands = [];
    let allCrops = [];

    function populateSelect(elementId, options, valueField, textField, selectedField = null) {
        const select = document.getElementById(elementId);

        if (elementId === 'id_land') {
            allLands = options;
            setupLandFiltering(options, valueField, textField, selectedField);
            return;
        }

        if (elementId === 'id_crop') {
            allCrops = options;
            setupCropFiltering(options, valueField, textField, selectedField);
            return;
        }

        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option[valueField];
            optionElement.textContent = option[textField];
            if (selectedField && option[selectedField]) {
                optionElement.selected = true;
            }
            select.appendChild(optionElement);
        });
    }

    function setupLandFiltering(options, valueField, textField, selectedField) {
        const select = document.getElementById('id_land');
        const searchInput = document.getElementById('landSearchInput');
        const clearButton = document.getElementById('clearLandSearch');

        updateLandOptions(options, valueField, textField, selectedField);

        searchInput.addEventListener('input', function () {
            const searchTerm = this.value.toLowerCase();
            const filteredOptions = options.filter(option =>
                option[textField].toLowerCase().includes(searchTerm)
            );
            updateLandOptions(filteredOptions, valueField, textField, selectedField);
        });

        clearButton.addEventListener('click', function () {
            searchInput.value = '';
            updateLandOptions(options, valueField, textField, selectedField);
            searchInput.focus();
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') e.preventDefault();
        });
    }

    function updateLandOptions(options, valueField, textField, selectedField) {
        const select = document.getElementById('id_land');
        const currentValue = select.value;

        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option[valueField];
            optionElement.textContent = option[textField];
            if (selectedField && option[selectedField] && !currentValue) {
                optionElement.selected = true;
            } else if (currentValue && option[valueField] == currentValue) {
                optionElement.selected = true;
            }
            select.appendChild(optionElement);
        });

        if (options.length === 0) {
            const noResultOption = document.createElement('option');
            noResultOption.value = '';
            noResultOption.textContent = '該当する圃場が見つかりません';
            noResultOption.disabled = true;
            select.appendChild(noResultOption);
        }
    }

    function setupCropFiltering(options, valueField, textField, selectedField) {
        const select = document.getElementById('id_crop');
        const searchInput = document.getElementById('cropSearchInput');
        const clearButton = document.getElementById('clearCropSearch');

        updateCropOptions(options, valueField, textField, selectedField);

        searchInput.addEventListener('input', function () {
            const searchTerm = this.value.toLowerCase();
            const filteredOptions = options.filter(option =>
                option[textField].toLowerCase().includes(searchTerm)
            );
            updateCropOptions(filteredOptions, valueField, textField, selectedField);
        });

        clearButton.addEventListener('click', function () {
            searchInput.value = '';
            updateCropOptions(options, valueField, textField, selectedField);
            searchInput.focus();
        });

        searchInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter') e.preventDefault();
        });
    }

    function updateCropOptions(options, valueField, textField, selectedField) {
        const select = document.getElementById('id_crop');
        const currentValue = select.value;

        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        options.forEach(option => {
            const optionElement = document.createElement('option');
            optionElement.value = option[valueField];
            optionElement.textContent = option[textField];
            if (currentValue && option[valueField] == currentValue) {
                optionElement.selected = true;
            }
            select.appendChild(optionElement);
        });

        if (options.length === 0) {
            const noResultOption = document.createElement('option');
            noResultOption.value = '';
            noResultOption.textContent = '該当する作物が見つかりません';
            noResultOption.disabled = true;
            select.appendChild(noResultOption);
        }
    }

    function submitForm() {
        btnSubmit.disabled = true;
        btnSubmit.innerHTML = '<i class="fas fa-spinner fa-spin"></i> 作成中...';
        errorDiv.style.display = 'none';

        const formData = new FormData(form);

        fetch(urls.land_ledger_create_ajax, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value
            }
        })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const landLedgerSelect = document.getElementById('land_ledger');
                    const newOption = document.createElement('option');
                    newOption.value = data.land_ledger.id;
                    newOption.textContent = data.land_ledger.display_name;
                    newOption.selected = true;
                    landLedgerSelect.appendChild(newOption);

                    bootstrap.Modal.getInstance(modal).hide();
                    showSuccessMessage(data.message);
                } else {
                    showError(data.message);
                }
            })
            .catch(error => {
                console.error('Error submitting form:', error);
                showError('帳簿作成中にエラーが発生しました。');
            })
            .finally(() => {
                btnSubmit.disabled = false;
                btnSubmit.innerHTML = '<i class="fas fa-save"></i> 帳簿を作成';
            });
    }

    function showError(message) {
        errorMessages.innerHTML = message.replace(/\n/g, '<br>');
        errorDiv.style.display = 'block';
    }

    function showSuccessMessage(message) {
        const alertHtml = `
            <div class="alert alert-success alert-dismissible fade show" role="alert">
                <i class="fas fa-check-circle"></i> ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>
        `;
        const container = document.querySelector('.container');
        const breadcrumb = container.querySelector('nav');
        breadcrumb.insertAdjacentHTML('afterend', alertHtml);
        setTimeout(() => {
            const alert = container.querySelector('.alert-success');
            if (alert) alert.remove();
        }, 5000);
    }
}
