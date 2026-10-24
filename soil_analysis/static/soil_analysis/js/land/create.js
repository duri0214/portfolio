/**
 * ドロップダウンを初期化し、デフォルトオプション「選択してください」を追加します
 * @param {HTMLSelectElement} selectElement - 初期化するセレクト要素
 */
function clearDropdown(selectElement) {
    const defaultOption = document.createElement('option')
    defaultOption.value = ""
    defaultOption.text = "選択してください"
    defaultOption.selected = true
    selectElement.appendChild(defaultOption)
}

/**
 * ドロップダウンにオプションリストを設定し、確実にenableにします
 *
 * @param {Array<{id: string, name: string}>} optionsData - 設定するオプションデータの配列
 * @param {HTMLSelectElement} selectElement - オプションを設定するセレクト要素
 */
function setDropdownList(optionsData, selectElement) {
    selectElement.disabled = false
    selectElement.classList.remove('disabled-field')
    optionsData.map(item => {
        const option = document.createElement('option')
        option.value = item.id
        option.text = item.name
        selectElement.appendChild(option)
    })
    updateAddressToCenterButton()
}

/**
 * 市区町村セレクトボックスを無効化し、初期状態にリセットします
 *
 * 都道府県が未選択の場合に実行され、データの整合性を保つため
 * 市区町村の選択を無効化します。
 */
function disableCitySelect() {
    const citySelect = document.getElementById("id_jma_city")
    if (!citySelect) return
    citySelect.innerHTML = ''
    clearDropdown(citySelect)
    citySelect.disabled = true
    citySelect.classList.add('disabled-field')
    updateAddressToCenterButton()
}

function updateAddressToCenterButton() {
    const prefectureSelect = document.getElementById("id_jma_prefecture")
    const citySelect = document.getElementById("id_jma_city")
    const button = document.getElementById("address-to-center-button")
    if (prefectureSelect && citySelect && button) {
        button.disabled = !prefectureSelect.value || !citySelect.value
    }
}

/**
 * 指定された都道府県 ID に基づいて都市データを取得し、それに応じて都市ドロップダウン オプションを設定します
 * 都道府県 ID が指定されていない場合、都市のドロップダウンはクリアされ無効化されます
 *
 * 【詳細な動作の流れ】
 * - 都道府県が選択されていない間: disableCitySelect()を実行してreturnで処理をスキップ
 * - 都道府県選択時のみ以下を実行:
 *   1. 市区町村セレクトボックスを一旦無効化（API通信中の状態）
 *   2. APIから市区町村データを非同期取得
 *   3. setDropdownList()でデータセット＋セレクトボックス有効化
 *
 * @param {string} prefectureId - 都道府県ID（空文字の場合は処理をスキップ）
 */
async function fetchCities(prefectureId) {
    const citySelect = document.getElementById("id_jma_city")
    if (!citySelect) return

    // 都道府県が選択されていない間は市区町村を無効化したままスキップ
    if (!prefectureId) {
        disableCitySelect()
        return
    }

    // ステップ1: 市区町村セレクトボックスを一旦無効化（API通信中の状態）
    citySelect.innerHTML = ''
    clearDropdown(citySelect)
    citySelect.disabled = true
    citySelect.classList.add('disabled-field')

    try {
        // ステップ2: APIから市区町村データを取得（この間disabled状態が続く）
        const response = await fetch(`/soil_analysis/prefecture/${prefectureId}/cities`)
        const data = await response.json()
        // ステップ3: データセット＋セレクトボックス有効化
        setDropdownList(data.cities, citySelect)
    } catch (error) {
        console.error('都市の取得に失敗しました:', error)
        disableCitySelect()
    }
}

// ページ読み込み時の初期化
document.addEventListener('DOMContentLoaded', function () {
    const prefectureSelect = document.getElementById("id_jma_prefecture")
    if (prefectureSelect) {
        // バリデーションエラー後の再表示など、都道府県に値が入っている場合はそのまま市区町村を取得
        if (prefectureSelect.value) {
            fetchCities(prefectureSelect.value)
        } else {
            disableCitySelect()
        }

        prefectureSelect.addEventListener("change", function () {
            fetchCities(this.value)
        })
    }

    const form = document.getElementById("land-create-form")
    const citySelect = document.getElementById("id_jma_city")
    const centerInput = document.getElementById("id_center")
    const addressToCenterButton = document.getElementById("address-to-center-button")
    const centerToAddressButton = document.getElementById("center-to-address-button")
    const feedback = document.getElementById("geocoding-feedback")

    function showFeedback(message, isError = false) {
        feedback.textContent = message
        feedback.classList.remove("d-none", "alert-success", "alert-danger", "alert-warning")
        feedback.classList.add(isError ? "alert-danger" : "alert-success")
    }

    async function postGeocoding(url, data) {
        const csrfToken = form.querySelector("[name=csrfmiddlewaretoken]").value
        const response = await fetch(url, {
            method: "POST",
            headers: { "X-CSRFToken": csrfToken },
            body: new URLSearchParams(data),
        })
        const responseData = await response.json()
        if (!response.ok) {
            throw new Error(responseData.message)
        }
        return responseData
    }

    if (citySelect) {
        citySelect.addEventListener("change", updateAddressToCenterButton)
    }

    if (addressToCenterButton) {
        addressToCenterButton.addEventListener("click", async function () {
            addressToCenterButton.disabled = true
            try {
                const response = await postGeocoding(form.dataset.addressGeocodeUrl, {
                    prefecture_id: prefectureSelect.value,
                    city_id: citySelect.value,
                })
                centerInput.value = response.center
                showFeedback("選択した地域の代表地点を中心座標へ設定しました。")
            } catch (error) {
                showFeedback(error.message, true)
            } finally {
                updateAddressToCenterButton()
            }
        })
    }

    if (centerToAddressButton) {
        centerToAddressButton.addEventListener("click", async function () {
            centerToAddressButton.disabled = true
            try {
                const response = await postGeocoding(form.dataset.coordinateGeocodeUrl, {
                    center: centerInput.value,
                })
                prefectureSelect.value = response.prefecture_id || ""
                if (response.prefecture_id) {
                    await fetchCities(response.prefecture_id)
                    citySelect.value = response.city_id || ""
                } else {
                    disableCitySelect()
                }
                updateAddressToCenterButton()
                showFeedback(response.message, !response.city_id)
            } catch (error) {
                showFeedback(error.message, true)
            } finally {
                centerToAddressButton.disabled = false
            }
        })
    }
})
