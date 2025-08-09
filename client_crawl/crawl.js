const { chromium } = require('playwright');

(async () => {
    let browser;
    const result = {};

    try {
        const url = process.argv[2];
        if (!url) {
            console.error('Usage: node crawl.js <URL>');
            process.exit(1);
        }

        browser = await chromium.launch({ headless: true });
        const page = await browser.newPage();
        await page.goto(url, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(3000);

        // Tìm và click nút specs
        const specsButton = page.locator(".button__show-modal-technical");
        if (await specsButton.count() === 0) {
            const altSelectors = [
                "button[data-modal='technical']",
                ".btn-technical",
                ".show-specs",
                "button:has-text('Thông số kỹ thuật')",
                "button:has-text('Chi tiết')"
            ];
            for (const sel of altSelectors) {
                if (await page.locator(sel).count() > 0) {
                    await page.click(sel);
                    break;
                }
            }
        } else {
            await specsButton.click();
        }

        // Chờ modal specs xuất hiện
        let modalSelector = ".teleport-modal_content .technical-content-section";
        try {
            await page.waitForSelector(modalSelector, { timeout: 10000 });
        } catch {
            const fallbacks = [
                ".modal .technical-content-section",
                ".popup .technical-content-section",
                ".overlay .technical-content-section",
                ".specifications-modal",
                ".tech-specs"
            ];
            for (const sel of fallbacks) {
                try {
                    await page.waitForSelector(sel, { timeout: 2000 });
                    modalSelector = sel;
                    break;
                } catch { }
            }
        }

        // Đọc specs
        const sections = await page.locator(modalSelector).all();
        for (const section of sections) {
            const title = (await section.locator("p.title").innerText()).trim();
            const rows = await section.locator("tr.technical-content-item").all();
            const specs = {};
            for (const row of rows) {
                const cells = await row.locator("td").all();
                if (cells.length >= 2) {
                    const key = (await cells[0].innerText()).trim();
                    const val = (await cells[1].innerText()).trim();
                    specs[key] = val;
                }
            }
            result[title] = specs;
        }

        console.log(JSON.stringify(result, null, 2));  // xuất ra stdout

    } catch (err) {
        console.error("Error in script:", err);
        process.exitCode = 1;
    } finally {
        if (browser) await browser.close();
    }
})();