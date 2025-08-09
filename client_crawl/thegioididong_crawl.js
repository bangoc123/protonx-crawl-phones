const { chromium } = require('playwright');

async function extractPriceAndPromotions(page) {
    const productData = {};

    // 1. Giá hiện tại, giá gốc, phần trăm giảm giá, trả góp
    const priceBox = await page.$('div.price-one');
    if (priceBox) {
        productData.current_price = await priceBox.$eval('p.box-price-present', el => el.textContent.trim()).catch(() => '');
        productData.original_price = await priceBox.$eval('p.box-price-old', el => el.textContent.trim()).catch(() => '');
        productData.discount = await priceBox.$eval('p.box-price-percent', el => el.textContent.trim()).catch(() => '');
        productData.installment_info = await priceBox.$eval('span.label--black', el => el.textContent.trim()).catch(() => '');
    } else {
        // Fallback: tìm trong block .bs_title .bs_price
        const bsPrice = await page.$('div.bs_title div.bs_price');
        if (bsPrice) {
            productData.current_price = await bsPrice.$eval('strong', el => el.textContent.trim()).catch(() => '');
            productData.original_price = await bsPrice.$eval('em', el => el.textContent.trim()).catch(() => '');
            productData.discount = await bsPrice.$eval('i', el => el.textContent.trim()).catch(() => '');
            productData.installment_info = '';
        } else {
            productData.current_price = '';
            productData.original_price = '';
            productData.discount = '';
            productData.installment_info = '';
        }
    }

    // 2. Địa điểm
    productData.location = await page.$eval('div#location-detail a', el => el.textContent.trim()).catch(() => '');

    // 3. Khuyến mãi
    const promoBox = await page.$('div.block__promo');
    if (promoBox) {
        productData.promo_title = await promoBox.$eval('p.pr-txtb', el => el.textContent.trim()).catch(() => '');
        productData.promo_list = await promoBox.$$eval('div.divb-right p', els =>
            els.map(el => el.textContent.trim())
        );
    } else {
        productData.promo_title = '';
        productData.promo_list = [];
    }

    // 4. Điểm tích lũy
    productData.loyalty_points = await page.$eval('p.loyalty__main__point', el => el.textContent.trim()).catch(() => '');

    return productData;
}

(async () => {
    let browser;
    try {
        const url = process.argv[2];
        if (!url) {
            console.error('Usage: node crawl.js <BASE_URL>');
            process.exit(1);
        }

        browser = await chromium.launch({ headless: true });
        const page = await browser.newPage();
        await page.goto(url, { waitUntil: 'domcontentloaded' });
        await page.waitForTimeout(2000);

        // 1. Lấy danh sách màu: text + href
        const colors = await page.$$eval(
            'div.scrolling_inner div.box03.color.group.desk a.box03__item',
            els => els.map(a => ({
                name: a.textContent.trim(),
                href: a.href
            }))
        );

        const results = [];
        for (const { name: color, href } of colors) {
            // 2. Đi tới URL của màu đó
            await page.goto(href, { waitUntil: 'domcontentloaded' });
            await page.waitForTimeout(2000);

            // 3. (Nếu cần) click specs modal
            //    await page.click('.button__show-modal-technical').catch(() => {});
            //    await page.waitForTimeout(1500);

            // 4. Extract price & promotions
            const data = await extractPriceAndPromotions(page);

            // 5. Gán thêm trường color, url
            results.push({ color, ...data });
        }

        // In ra mảng kết quả
        console.log(JSON.stringify(results, null, 2));

    } catch (err) {
        console.error('Error in script:', err);
        process.exitCode = 1;
    } finally {
        if (browser) await browser.close();
    }
})();
