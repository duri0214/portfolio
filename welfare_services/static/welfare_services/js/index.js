/**
 * インデックスページで使用するJavaScript機能
 * - スクロールアニメーション
 * - 施設検索フィルター
 */

document.addEventListener('DOMContentLoaded', function () {
    // スクロールアニメーション
    const scrollElements = document.querySelectorAll('.scroll-animation');

    // 要素が表示範囲内にあるか確認
    const elementInView = (el, threshold = 0.8) => {
        const elementRect = el.getBoundingClientRect();
        const windowHeight = window.innerHeight || document.documentElement.clientHeight;

        // 要素の上部が画面内に入っているか、または
        // 要素の下部が画面内に入っているか確認
        return (
            (elementRect.top <= windowHeight * threshold) &&
            (elementRect.bottom >= 0)
        );
    };

    // 要素を表示
    const displayScrollElement = (element) => {
        element.classList.add('animate-fadeInUp');
        // アニメーション後に一度だけ実行されるようにマーク
        element.dataset.animated = 'true';
    };

    // スクロール時のアニメーション処理
    const handleScrollAnimation = () => {
        scrollElements.forEach((el) => {
            // まだアニメーションされていない要素だけを処理
            if (!el.dataset.animated && elementInView(el)) {
                displayScrollElement(el);
            }
        });
    };

    // 最適化されたスクロールイベント（スロットリング）
    let scrollTimeout;
    window.addEventListener('scroll', () => {
        if (!scrollTimeout) {
            scrollTimeout = setTimeout(() => {
                handleScrollAnimation();
                scrollTimeout = null;
            }, 100); // 100ms間隔でのみ実行
        }
    });

    // 初期表示時にも実行
    handleScrollAnimation();

    // 施設検索フィルター
    const facilityFilter = document.getElementById('facility-filter');
    if (facilityFilter) {
        facilityFilter.addEventListener('input', function () {
            const filterValue = this.value.toLowerCase();
            const facilityItems = document.querySelectorAll('.facility-item');

            facilityItems.forEach(item => {
                const facilityName = item.querySelector('.facility-name').textContent.toLowerCase();
                const facilityAddress = item.querySelector('.facility-address').textContent.toLowerCase();

                if (facilityName.includes(filterValue) || facilityAddress.includes(filterValue)) {
                    item.style.display = '';
                } else {
                    item.style.display = 'none';
                }
            });
        });
    }
});
