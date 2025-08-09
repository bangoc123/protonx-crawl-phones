const { chromium } = require('playwright');

(async () => {
    const browser = await chromium.launch({ headless: false });
    const context = await browser.newContext({
        userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        locale: 'vi-VN',
        timezoneId: 'Asia/Ho_Chi_Minh'
    });
    const page = await context.newPage();

    try {
        const url = process.argv[2];

        if (!url) {
            console.error('Usage: node crawl.js <URL>');
            process.exit(1);
        }

        console.log("Navigating to page...");
        await page.goto(url, {
            // waitUntil: "networkidle" 
        });

        // Wait longer for all API calls to complete
        console.log("Waiting for page to fully load and make API calls...");
        await page.waitForTimeout(3000);

        // PHIÊN BẢN CẢI TIẾN - ĐO MEMORY AN TOÀN HƠN:
        console.log('📊 Measuring memory after initial load...');
        const memInfo = await page.evaluate(async () => {
            const memoryInfo = {};

            try {
                // Kiểm tra cross-origin isolation trước
                if (typeof window.crossOriginIsolated !== 'undefined' && window.crossOriginIsolated) {
                    console.log('✅ Cross-origin isolated context detected');

                    if (typeof performance.measureUserAgentSpecificMemory === 'function') {
                        try {
                            const result = await performance.measureUserAgentSpecificMemory();
                            memoryInfo.advanced = {
                                totalBytes: result.bytes,
                                breakdown: result.breakdown
                            };
                            console.log('✅ Advanced memory measurement successful');
                        } catch (advancedErr) {
                            memoryInfo.advancedError = `Advanced memory API error: ${advancedErr.message}`;
                            console.log('⚠️ Advanced memory measurement failed:', advancedErr.message);
                        }
                    } else {
                        memoryInfo.advancedError = 'measureUserAgentSpecificMemory not available';
                    }
                } else {
                    memoryInfo.crossOriginNote = 'Not in cross-origin isolated context';
                }

                // Fallback sang basic memory API
                if (typeof performance !== 'undefined' && performance.memory) {
                    memoryInfo.basic = {
                        usedJSHeapSize: performance.memory.usedJSHeapSize,
                        totalJSHeapSize: performance.memory.totalJSHeapSize,
                        jsHeapSizeLimit: performance.memory.jsHeapSizeLimit
                    };
                    console.log('✅ Basic memory measurement successful');
                } else {
                    memoryInfo.basicError = 'Basic memory API not supported';
                }

                // Thêm thông tin browser và context
                memoryInfo.userAgent = navigator.userAgent;
                memoryInfo.timestamp = new Date().toISOString();

            } catch (generalError) {
                memoryInfo.error = `General memory measurement error: ${generalError.message}`;
                console.log('❌ General memory measurement error:', generalError.message);
            }

            return memoryInfo;
        });

        console.log('📦 Memory info:', JSON.stringify(memInfo, null, 2));

        // Inject the SKU extraction functions into the page
        await page.addScriptTag({
            content: `
                // STEP 1: Find the "Xem tất cả thông số" button function
                function findSpecsButton() {
                    const buttons = document.querySelectorAll('button');
                    
                    for (const button of buttons) {
                        const spans = button.querySelectorAll('span');
                        const spanTexts = Array.from(spans).map(span => span.innerText.trim());
                        const hasTargetText = spanTexts.some(text => text.includes('Xem tất cả thông số'));
                        
                        if (hasTargetText) {
                            return button;
                        }
                    }
                    return null;
                }

                // STEP 2: Close specs panel function
                async function closeSpecsPanel() {
                    console.log('🚪 Attempting to close specs panel...');
                    
                    // Try multiple methods to close the panel
                    const closeMethods = [
                        // Method 1: Click on the backdrop (PREFERRED METHOD)
                        () => {
                            const backdrop = document.querySelector('.Backdrop_backdrop__A7yIC.Backdrop_darkMode__eqwkh.Backdrop_showBackdrop__xvyWm');
                            if (backdrop) {
                                console.log('🌑 Found backdrop with all classes, clicking...');
                                backdrop.click();
                                return true;
                            }
                            return false;
                        },
                        
                        // Method 2: Try individual backdrop classes
                        () => {
                            const backdrops = [
                                '.Backdrop_backdrop__A7yIC',
                                '.Backdrop_darkMode__eqwkh', 
                                '.Backdrop_showBackdrop__xvyWm'
                            ];
                            
                            for (const selector of backdrops) {
                                const element = document.querySelector(selector);
                                if (element) {
                                    console.log(\`🌑 Found backdrop (\${selector}), clicking...\`);
                                    element.click();
                                    return true;
                                }
                            }
                            return false;
                        },
                        
                        // Method 3: Press Escape key
                        () => {
                            console.log('⌨️ Trying Escape key...');
                            document.dispatchEvent(new KeyboardEvent('keydown', {
                                key: 'Escape',
                                code: 'Escape',
                                keyCode: 27,
                                which: 27,
                                bubbles: true
                            }));
                            return true;
                        }
                    ];
                    
                    // Try each method
                    for (let i = 0; i < closeMethods.length; i++) {
                        try {
                            const success = closeMethods[i]();
                            if (success) {
                                // Wait to see if panel closes
                                await new Promise(resolve => setTimeout(resolve, 1500));
                                
                                // Check if panel is actually closed
                                const backdropStillExists = document.querySelector('.Backdrop_backdrop__A7yIC') || 
                                                           document.querySelector('.Backdrop_showBackdrop__xvyWm');
                                const specPanelStillExists = document.querySelector('[id^="spec-item-"]') ||
                                                           document.querySelector('.Swipeable_swipeable__BTB2L');
                                
                                if (!backdropStillExists && !specPanelStillExists) {
                                    console.log(\`✅ Panel closed successfully (method \${i + 1})\`);
                                    return true;
                                } else {
                                    console.log(\`⚠️ Panel still visible after method \${i + 1}\`);
                                }
                            }
                        } catch (error) {
                            console.log(\`❌ Error in close method \${i + 1}:\`, error.message);
                        }
                    }
                    
                    console.log('🤷 Could not close panel, continuing anyway...');
                    return false;
                }

                // STEP 3: Extract specifications function
                function extractSpecifications() {
                    const specItems = [];
                    const specElements = document.querySelectorAll('[id^="spec-item-"]');
                    
                    console.log(\`📋 Found \${specElements.length} spec sections to extract...\`);
                    
                    specElements.forEach((specElement) => {
                        const titleElement = specElement.querySelector('.b2-semibold span, .text-textOnWhitePrimary.b2-semibold span');
                        const sectionTitle = titleElement ? titleElement.textContent.trim() : 'Unknown Section';
                        
                        const specRows = specElement.querySelectorAll('.flex.gap-2.border-b, .flex.gap-2.border-b-iconDividerOnWhite');
                        const specifications = [];
                        
                        specRows.forEach(row => {
                            const labelElement = row.querySelector('.text-textOnWhiteSecondary span') || 
                                                row.querySelector('[class*="w-2/5"] span') ||
                                                row.querySelector('.w-2\\/5 span');
                            const valueElement = row.querySelector('.flex-1');
                            
                            if (labelElement && valueElement) {
                                const label = labelElement.textContent.trim();
                                const paragraphs = valueElement.querySelectorAll('p');
                                let value;
                                
                                if (paragraphs.length > 0) {
                                    value = Array.from(paragraphs).map(p => p.textContent.trim());
                                } else {
                                    value = valueElement.textContent.trim();
                                }
                                
                                specifications.push({ label: label, value: value });
                            }
                        });
                        
                        specItems.push({
                            id: specElement.id,
                            title: sectionTitle,
                            specifications: specifications,
                            specCount: specifications.length
                        });
                    });
                    
                    console.log(\`✅ Extracted \${specItems.length} sections with \${specItems.reduce((sum, section) => sum + section.specCount, 0)} total specs\`);
                    
                    return specItems;
                }

                // STEP 4: Find product variants function
                function findProductVariants() {
                    const storageSection = Array.from(document.querySelectorAll('span')).find(span => 
                        span.textContent.trim() === 'Dung lượng'
                    )?.closest('.flex.flex-col');
                    
                    const colorSection = Array.from(document.querySelectorAll('span')).find(span => 
                        span.textContent.trim() === 'Màu sắc'
                    )?.closest('.flex.flex-col');
                    
                    let storageButtons = [];
                    let colorButtons = [];
                    
                    if (storageSection) {
                        const storageButtonContainer = storageSection.querySelector('.flex.flex-wrap.gap-2');
                        if (storageButtonContainer) {
                            storageButtons = Array.from(storageButtonContainer.querySelectorAll('button'));
                            console.log(\`📦 Found \${storageButtons.length} storage options\`);
                        }
                    }
                    
                    if (colorSection) {
                        const colorButtonContainer = colorSection.querySelector('.flex.flex-wrap.gap-2');
                        if (colorButtonContainer) {
                            colorButtons = Array.from(colorButtonContainer.querySelectorAll('button'));
                            console.log(\`🎨 Found \${colorButtons.length} color options\`);
                        }
                    }
                    
                    return { storageButtons, colorButtons };
                }

                // Helper function to capture current state including SKU
                function captureCurrentState(storage, color) {
                    const state = { price: null, availability: null, sku: null };
                    
                    // Try to capture price
                    const priceSelectors = ['[data-testid*="price"]', '.price-product', '[class*="price-product"]'];
                    for (const selector of priceSelectors) {
                        const elements = document.querySelectorAll(selector);
                        for (const element of elements) {
                            const text = element.textContent;
                            if (text.includes('đ') || text.includes('VND') || /\\d+[.,]\\d+/.test(text)) {
                                state.price = text.trim();
                                break;
                            }
                        }
                        if (state.price) break;
                    }
                    
                    // Try to capture SKU from URL
                    const urlMatch = window.location.href.match(/sku[=\\/](\\w+)/i);
                    if (urlMatch) {
                        state.sku = urlMatch[1];
                    }
                    
                    return state;
                }

                // Main function to process all variants and extract SKUs/specs
                async function processAllVariantsAndExtractData() {
                    console.log("🚀 Starting MEGA process: All variants → Extract specs & SKUs → Close panels");
                    
                    const initialVariants = findProductVariants();
                    
                    if (initialVariants.storageButtons.length === 0 || initialVariants.colorButtons.length === 0) {
                        console.log("❌ Cannot proceed - missing storage or color buttons");
                        return { error: "Missing variants", results: [] };
                    }
                    
                    const totalCombinations = initialVariants.storageButtons.length * initialVariants.colorButtons.length;
                    console.log(\`🎯 Will process \${totalCombinations} combinations\`);
                    
                    const allResults = [];
                    
                    // Loop through each storage capacity
                    for (let storageIndex = 0; storageIndex < initialVariants.storageButtons.length; storageIndex++) {
                        
                        // Re-find storage buttons (they may have changed in DOM)
                        const currentStorageSection = Array.from(document.querySelectorAll('span')).find(span => 
                            span.textContent.trim() === 'Dung lượng'
                        )?.closest('.flex.flex-col');
                        
                        const currentStorageButtonContainer = currentStorageSection?.querySelector('.flex.flex-wrap.gap-2');
                        const currentStorageButtons = currentStorageButtonContainer ? 
                            Array.from(currentStorageButtonContainer.querySelectorAll('button')) : [];
                        
                        if (storageIndex >= currentStorageButtons.length) {
                            continue;
                        }
                        
                        const storageButton = currentStorageButtons[storageIndex];
                        const storageText = storageButton.querySelector('span.b2-medium')?.textContent.trim() || \`Storage \${storageIndex + 1}\`;
                        
                        console.log(\`📦 PROCESSING STORAGE: \${storageText}\`);
                        
                        // Click storage button
                        storageButton.click();
                        await new Promise(resolve => setTimeout(resolve, 2000));
                        
                        // Loop through each color for this storage
                        for (let colorIndex = 0; colorIndex < initialVariants.colorButtons.length; colorIndex++) {
                            
                            // Re-find color buttons
                            const currentColorSection = Array.from(document.querySelectorAll('span')).find(span => 
                                span.textContent.trim() === 'Màu sắc'
                            )?.closest('.flex.flex-col');
                            
                            const currentColorButtonContainer = currentColorSection?.querySelector('.flex.flex-wrap.gap-2');
                            const currentColorButtons = currentColorButtonContainer ? 
                                Array.from(currentColorButtonContainer.querySelectorAll('button')) : [];
                            
                            if (colorIndex >= currentColorButtons.length) {
                                continue;
                            }
                            
                            const colorButton = currentColorButtons[colorIndex];
                            const colorText = colorButton.querySelector('span.b2-medium')?.textContent.trim() || \`Color \${colorIndex + 1}\`;
                            
                            console.log(\`🎨 PROCESSING COLOR: \${colorText}\`);
                            
                            // Click color button
                            colorButton.click();
                            await new Promise(resolve => setTimeout(resolve, 1500));
                            
                            // Capture current state (price, SKU, etc.)
                            const currentState = captureCurrentState(storageText, colorText);
                            
                            console.log(\`🔍 EXTRACTING SPECS for \${storageText} + \${colorText}...\`);
                            
                            const specsButton = findSpecsButton();
                            if (specsButton) {
                                // Click specs button
                                specsButton.click();
                                console.log('📋 Specs button clicked');
                                
                                // Wait for specs to load
                                await new Promise(resolve => setTimeout(resolve, 4000));
                                
                                // Extract specifications
                                const specifications = extractSpecifications();
                                
                                // Combine everything into result
                                const combinationResult = {
                                    storage: storageText,
                                    color: colorText,
                                    timestamp: new Date().toLocaleTimeString(),
                                    price: currentState.price,
                                    availability: currentState.availability,
                                    sku: currentState.sku,
                                    url: window.location.href,
                                    specifications: specifications,
                                    totalSpecs: specifications.reduce((sum, section) => sum + section.specCount, 0)
                                };
                                
                                allResults.push(combinationResult);
                                console.log(\`✅ EXTRACTED: \${combinationResult.totalSpecs} specs, SKU: \${currentState.sku || 'Not found'}\`);
                                
                                // CLOSE THE SPECS PANEL
                                await closeSpecsPanel();
                                await new Promise(resolve => setTimeout(resolve, 2000));
                                
                            } else {
                                console.log('❌ Specs button not found');
                                allResults.push({
                                    storage: storageText,
                                    color: colorText,
                                    timestamp: new Date().toLocaleTimeString(),
                                    price: currentState.price,
                                    sku: currentState.sku,
                                    specifications: [],
                                    totalSpecs: 0,
                                    error: "Specs button not found"
                                });
                            }
                            
                            console.log(\`📊 Progress: \${allResults.length}/\${totalCombinations}\`);
                        }
                    }
                    
                    console.log(\`🎉 COMPLETED! Processed \${allResults.length} combinations\`);
                    return { results: allResults, totalProcessed: allResults.length };
                }

                // Make function available globally
                window.processAllVariantsAndExtractData = processAllVariantsAndExtractData;
            `
        });

        // Execute the SKU extraction process
        // Thêm memory monitoring trong quá trình crawl (tùy chọn)
        const monitorMemoryDuringCrawl = async () => {
            const quickMemCheck = await page.evaluate(() => {
                if (performance.memory) {
                    return {
                        used: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024) + 'MB',
                        total: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024) + 'MB'
                    };
                }
                return null;
            });

            if (quickMemCheck) {
                console.log(`🧠 Current memory: ${quickMemCheck.used}/${quickMemCheck.total}`);
            }
        };

        // Gọi memory monitor định kỳ (không bắt buộc)
        const memoryInterval = setInterval(monitorMemoryDuringCrawl, 10000); // Mỗi 10 giây

        const results = await page.evaluate(async () => {
            return await window.processAllVariantsAndExtractData();
        });

        // Dừng memory monitoring
        clearInterval(memoryInterval);

        // Log kết quả cuối cùng
        console.log("===results===");
        console.log(results);
        console.log("================================================================================\n");

        // Đo memory sau khi crawl xong
        console.log('📊 Final memory measurement...');
        const finalMemInfo = await page.evaluate(() => {
            if (performance.memory) {
                return {
                    usedJSHeapSize: performance.memory.usedJSHeapSize,
                    totalJSHeapSize: performance.memory.totalJSHeapSize,
                    usedMB: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                    totalMB: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
                };
            }
            return { error: 'Memory API not available' };
        });
        console.log('📦 Final memory info:', finalMemInfo);

        // Phần xử lý kết quả...
        console.log("\n=== EXTRACTION RESULTS ===");
        console.log(`Total combinations processed: ${results.totalProcessed}`);

        if (results.results && results.results.length > 0) {
            // Save results...
            const fs = require('fs');

            // Thêm memory info vào file kết quả
            const finalResults = {
                ...results,
                memoryInfo: {
                    initial: memInfo,
                    final: finalMemInfo,
                    timestamp: new Date().toISOString()
                }
            };

            fs.writeFileSync('product-variants-data.json', JSON.stringify(finalResults, null, 2));
            console.log("\n💾 Results with memory info saved to 'product-variants-data.json'");
        }

        console.log("\n✨ Process completed successfully!");

    } catch (error) {
        console.error('Error:', error.message);

        // Log memory info khi có lỗi
        try {
            const errorMemInfo = await page.evaluate(() => {
                if (performance.memory) {
                    return {
                        usedMB: Math.round(performance.memory.usedJSHeapSize / 1024 / 1024),
                        totalMB: Math.round(performance.memory.totalJSHeapSize / 1024 / 1024)
                    };
                }
                return null;
            });

            if (errorMemInfo) {
                console.log('💥 Memory at error:', errorMemInfo);
            }
        } catch (memErr) {
            console.log('Cannot measure memory at error');
        }

        await page.screenshot({ path: 'error-screenshot.png', fullPage: true });
        console.log("Error screenshot saved");
    } finally {
        await context.close();
        await browser.close();
    }
})();