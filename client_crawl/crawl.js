const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: true }); // Set to false for debugging
    const page = await browser.newPage();
    
    try {
        console.log("Navigating to page...");
        await page.goto("https://cellphones.com.vn/dien-thoai-xiaomi-15.html", { 
            waitUntil: "domcontentloaded" 
        });

        // Wait a bit for page to fully load
        await page.waitForTimeout(3000);

        // Check if the button exists
        console.log("Looking for specs button...");
        const specsButton = page.locator(".button__show-modal-technical");
        const buttonCount = await specsButton.count();
        console.log(`Found ${buttonCount} specs button(s)`);

        if (buttonCount === 0) {
            // Try alternative selectors
            const altSelectors = [
                "button[data-modal='technical']",
                ".btn-technical",
                ".show-specs",
                "button:has-text('Thông số kỹ thuật')",
                "button:has-text('Chi tiết')"
            ];

            for (const selector of altSelectors) {
                const count = await page.locator(selector).count();
                if (count > 0) {
                    console.log(`Found button with selector: ${selector}`);
                    await page.click(selector);
                    break;
                }
            }
        } else {
            console.log("Clicking specs button...");
            await specsButton.click();
        }

        // Wait and check for modal
        console.log("Waiting for modal to appear...");
        
        try {
            await page.waitForSelector(".teleport-modal_content .technical-content-section", {
                timeout: 10000
            });
            console.log("Modal appeared!");
        } catch (error) {
            console.log("Modal didn't appear, trying alternative selectors...");
            
            // Try alternative modal selectors
            const modalSelectors = [
                ".modal .technical-content-section",
                ".popup .technical-content-section",
                ".overlay .technical-content-section",
                ".specifications-modal",
                ".tech-specs"
            ];

            let modalFound = false;
            for (const selector of modalSelectors) {
                try {
                    await page.waitForSelector(selector, { timeout: 2000 });
                    console.log(`Found modal with selector: ${selector}`);
                    modalFound = true;
                    break;
                } catch (e) {
                    // Continue to next selector
                }
            }

            if (!modalFound) {
                console.log("No modal found. Taking screenshot for debugging...");
                await page.screenshot({ path: 'debug-screenshot.png', fullPage: true });
                console.log("Screenshot saved as debug-screenshot.png");
                return;
            }
        }

        const sections = await page.locator(".teleport-modal_content .technical-content-section").all();
        console.log(`Found ${sections.length} sections`);

        for (const section of sections) {
            const title = await section.locator("p.title").innerText();
            console.log(`\n=== ${title.trim()} ===`);

            const rows = await section.locator("tr.technical-content-item").all();
            
            for (const row of rows) {
                const cells = await row.locator("td").all();
                if (cells.length >= 2) {
                    const key = await cells[0].innerText();
                    const value = await cells[1].innerText();
                    console.log(`${key.trim()}: ${value.trim()}`);
                }
            }
        }

    } catch (error) {
        console.error('Error:', error.message);
        await page.screenshot({ path: 'error-screenshot.png', fullPage: true });
        console.log("Error screenshot saved");
    } finally {
        await browser.close();
    }
})();