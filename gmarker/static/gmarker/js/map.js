/**
 * @fileoverview Google Maps APIを使用して地図表示とマーカー管理を行うモジュール
 *
 * このファイルは以下の機能を提供します：
 * - Google Maps APIの初期化と設定
 * - Advanced Markersの対応確認と利用
 * - マーカーデータの管理と情報ウィンドウの表示
 *
 * @requires google.maps
 * @requires google.maps.marker.AdvancedMarkerElement
 */

/** グローバル変数：現在開いている情報ウィンドウのインスタンス */
let infoWindow;

/**
 * マーカーデータを管理するクラス
 *
 * @class
 * @description Google Mapsマーカーに関連するデータを整形・保持するためのクラス
 */
class MarkerData {
    /**
     * MarkerDataインスタンスを作成
     *
     * @constructor
     * @param {Object} data - 場所に関するデータオブジェクト
     * @param {Object} data.location - 座標情報を含むオブジェクト
     * @param {number} data.location.lat - 緯度
     * @param {number} data.location.lng - 経度
     * @param {string} [data.name] - 場所の名前（省略時は「マーカー」）
     * @param {string} [data.place_id] - Google Place ID
     * @param {number} [data.rating] - 評価点数
     * @throws {Error} 座標情報が不正な場合にエラーをスロー
     */
    constructor(data) {
        // データのチェック
        if (!data || !data.location) {
            console.error('Invalid data passed to MarkerData:', data);
            throw new Error('Invalid marker data: location missing');
        }

        if (typeof data.location.lat !== 'number' || typeof data.location.lng !== 'number') {
            console.error('Invalid location coordinates:', data.location);
            throw new Error('Invalid location coordinates');
        }

        this.lat = data.location.lat;
        this.lng = data.location.lng;
        this.title = data.name || "マーカー";
        this.placeId = data.place_id;
        this.rating = data.rating;
    }

    /**
     * マーカーの情報ウィンドウに表示するHTML文字列を生成
     *
     * @returns {string} マーカー情報を表示するためのHTML
     */
    toHtml() {
        return `
          <div>
            <p>${this.title}</p>
            <p>Place ID: ${this.placeId}<br>lat,lng: ${this.lat},${this.lng}<br>rating: ${this.rating}</p>
          </div>
        `;
    }
}

/**
 * Google Mapsを初期化し、マーカーを配置する
 *
 * @function
 * @param {Object} jsonData - 地図初期化に必要なデータ
 * @param {Object} jsonData.center - 中心座標
 * @param {number} jsonData.center.lat - 中心緯度
 * @param {number} jsonData.center.lng - 中心経度
 * @param {Array} jsonData.places - 表示する場所のデータ配列
 * @param {string} [jsonData.mapId] - GCP上で作成した地図ID
 * @returns {google.maps.Map|undefined} 作成されたMapオブジェクト、またはエラー時はundefined
 */
function initMap(jsonData) {
    try {
        if (!jsonData) {
            console.error("jsonData is not defined.");
            return;
        }

        const {Map} = google.maps;

        const options = {
            zoom: 14,
            center: new google.maps.LatLng(jsonData.center.lat, jsonData.center.lng),
            mapTypeId: google.maps.MapTypeId.ROADMAP,
            mapTypeControl: false,
            keyboardShortcuts: false,
            streetViewControl: false,
            fullscreenControl: false,
            scrollwheel: true
        };

        // mapIdはGCP上で作成した地図スタイル設定やAdvanced Markersなどの高度な機能利用に必要な識別子
        if (jsonData.mapId) {
            options.mapId = jsonData.mapId;
            console.log(`Using Map ID: ${jsonData.mapId}`);
        } else {
            console.warn('No Map ID provided. Using default Google Maps style.');
        }

        map = new Map(document.getElementById("map_canvas1"), options);

        // Advanced Markerが利用可能かチェック
        if (google.maps.marker && google.maps.marker.AdvancedMarkerElement) {
            console.log('Using Advanced Markers');
            createMarkersFromData(jsonData.places, google.maps.marker.AdvancedMarkerElement, map);
        } else {
            console.warn('Advanced Markers not available');
        }

    } catch (e) {
        console.error("Google Maps API の初期化エラー:", e);
        alert("地図の読み込みに失敗しました。インターネット接続を確認してください。");
    }
}

/**
 * Advanced Markersを使用して地図上にマーカーを作成・配置する
 *
 * @function
 * @param {Array} places - 場所データの配列
 * @param {Class} AdvancedMarkerElement - Google Maps APIのAdvancedMarkerElementクラス
 * @param {google.maps.Map} map - マーカーを配置する地図オブジェクト
 * @returns {Array|undefined} 作成されたマーカーと関連データの配列、またはエラー時はundefined
 */
function createMarkersFromData(places, AdvancedMarkerElement, map) {
    if (!map || !places || !AdvancedMarkerElement) {
        console.error("Missing map, places, or AdvancedMarkerElement");
        return;
    }
    console.log('Places data received:', places);

    places.map(place => {
        try {
            // データ構造のチェック
            if (!place.location || (!place.location.lat && !place.location.lat === 0)) {
                console.error('Invalid place data, missing location coordinates:', place);
                return;
            }

            const markerData = new MarkerData(place);
            console.log('Creating marker for:', markerData);

            const marker = new AdvancedMarkerElement({
                position: new google.maps.LatLng(markerData.lat, markerData.lng),
                map: map,
                title: markerData.title,
                gmpClickable: true
            });

            marker.addEventListener('gmp-click', () => {
                showInfoWindow(marker, markerData.toHtml());
            });

            return {marker, data: markerData};
        } catch (error) {
            console.error('Error creating marker for place:', place, error);
            return null;
        }
    }).filter(item => item !== null);
}

/**
 * マーカークリック時に情報ウィンドウを表示する
 *
 * @function
 * @param {google.maps.marker.AdvancedMarkerElement|google.maps.Marker} marker - クリックされたマーカー
 * @param {string} content - 情報ウィンドウに表示するHTML
 */
function showInfoWindow(marker, content) {
    if (infoWindow) {
        infoWindow.close();
    }
    infoWindow = new google.maps.InfoWindow({content});
    infoWindow.open({
        anchor: marker,
        map: map
    });
}
