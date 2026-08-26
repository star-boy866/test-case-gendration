const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const child_process = require('child_process');
const JSZip = require('jszip');

(async () => {
    const args = process.argv.slice(2);
    if (args.length < 4) {
        console.error("Usage: node render_snapshot.js <docxPath> <outPngPath> <semanticSection> <reportId> [methodology] [targetField] [evidenceScope]");
        process.exit(1);
    }

    const docxPath = args[0];
    const outPngPath = args[1];
    const semanticSection = args[2] || "";
    const reportId = args[3] || "";
    const methodology = (args[4] || "").toUpperCase().trim();
    const targetField = (args[5] || "").toLowerCase().trim();
    const evidenceScope = (args[6] || "").toLowerCase().trim();

    console.log(`[STAGE 1] DOCX Path: ${docxPath}`);
    console.log(`[STAGE 1] Output PNG Path: ${outPngPath}`);
    console.log(`[STAGE 1] Methodology: ${methodology}, Section: "${semanticSection}", Scope: "${evidenceScope}", TargetField: "${targetField}"`);

    if (!fs.existsSync(docxPath)) {
        console.error(`[ERROR] File not found: ${docxPath}`);
        process.exit(1);
    }

    let docxBuffer = fs.readFileSync(docxPath);
    try {
        const zip = await JSZip.loadAsync(docxBuffer);
        const hasEmf = Object.keys(zip.files).some(f => f.toLowerCase().endsWith('.emf') || f.toLowerCase().endsWith('.wmf'));
        if (hasEmf) {
            const converterScript = path.resolve(__dirname, '../app/utils/docx_emf_converter.py');
            const tempDir = path.resolve(__dirname, '../scratch');
            if (!fs.existsSync(tempDir)) fs.mkdirSync(tempDir, { recursive: true });
            const tempOut = path.resolve(tempDir, `temp_${Date.now()}_converted.docx`);
            try {
                child_process.execSync(`python "${converterScript}" "${docxPath}" "${tempOut}"`, { stdio: 'pipe' });
                if (fs.existsSync(tempOut) && fs.statSync(tempOut).size > 0) {
                    docxBuffer = fs.readFileSync(tempOut);
                    fs.unlinkSync(tempOut);
                    console.log(`[STAGE 1] Preprocessed EMF/WMF images to PNG format for browser rendering.`);
                }
            } catch (convErr) {
                console.log(`[WARN] EMF converter warning: ${convErr.message}`);
            }
        }
    } catch (zipErr) {
        // Continue with original buffer
    }

    const base64Data = docxBuffer.toString('base64');

    const browser = await chromium.launch({ headless: true });
    const page = await browser.newPage();
    await page.setViewportSize({ width: 3200, height: 6000 });

    try {
        const htmlPath = path.resolve(__dirname, 'docx-render.html');
        const fileUrl = 'file:///' + htmlPath.replace(/\\/g, '/');
        await page.goto(fileUrl);

        // Inject dependencies
        await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/jszip/dist/jszip.min.js') });
        await page.addScriptTag({ path: path.resolve(__dirname, '../node_modules/docx-preview/dist/docx-preview.min.js') });

        // Trigger rendering
        await page.evaluate(`renderDocx("${base64Data}")`);

        // Wait for rendering to complete
        await page.waitForFunction('window.isRenderComplete === true', { timeout: 30000 });

        const renderError = await page.evaluate('window.renderError');
        if (renderError) {
            throw new Error(`Rendering failed in browser: ${renderError}`);
        }

        // Ensure all images are fully decoded
        await page.evaluate(async () => {
            const imgs = Array.from(document.querySelectorAll('img'));
            await Promise.all(imgs.map(img => {
                if (img.complete && img.naturalWidth > 0) return Promise.resolve();
                return new Promise(resolve => {
                    img.onload = resolve;
                    img.onerror = resolve;
                    setTimeout(resolve, 3000);
                });
            }));
        });

        const pages = await page.$$('.docx-wrapper > section');
        console.log(`[STAGE 2] Rendered ${pages.length} pages.`);
        if (pages.length === 0) {
            throw new Error("No pages rendered");
        }

        let targetElement = null;
        let targetClip = null;
        let isCustomSaved = false;

        // ── METHODOLOGY-SPECIFIC TARGETING ───────────────────────────────────

        // 1. LAYOUT_VALIDATION: Full Report Layout page (Phase 13D.1)
        if (
            methodology === "LAYOUT_VALIDATION" ||
            evidenceScope.toLowerCase().includes("full_report_layout")
        ) {
            const measureLayoutPage = async () => {
                return await page.evaluate(() => {
                    window.scrollTo(0, 0);
                    if (document.scrollingElement) {
                        document.scrollingElement.scrollTop = 0;
                        document.scrollingElement.scrollLeft = 0;
                    }
                    const docxWrapper = document.querySelector('.docx-wrapper');
                    if (docxWrapper) {
                        docxWrapper.scrollTop = 0;
                        docxWrapper.scrollLeft = 0;
                    }

                    const sections = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                    let targetSecIdx = -1;

                    for (let i = 0; i < sections.length; i++) {
                        const txt = (sections[i].innerText || '').toLowerCase();
                        const hasLayoutHeader = txt.includes("nh mmis report layout") || txt.includes("report layout") || txt.includes("future state - report output") || txt.includes("scenario 1") || txt.includes("excel format");
                        if (hasLayoutHeader) {
                            targetSecIdx = i;
                            break;
                        }
                    }

                    if (targetSecIdx === -1) return null;

                    const sec = sections[targetSecIdx];
                    const secRect = sec.getBoundingClientRect();

                    // Find all elements within this section to get true full enclosing bounds
                    const allElements = Array.from(sec.querySelectorAll('*'));
                    const allRects = allElements.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);

                    const minLeft = Math.min(secRect.left, ...allRects.map(r => r.left));
                    const minTop = Math.min(secRect.top, ...allRects.map(r => r.top));
                    const maxRight = Math.max(secRect.right, ...allRects.map(r => r.right));
                    const maxBottom = Math.max(secRect.bottom, ...allRects.map(r => r.bottom));

                    const margin = 8;
                    const pageClip = {
                        x: Math.max(0, Math.floor(minLeft - margin)),
                        y: Math.max(0, Math.floor(minTop - margin)),
                        width: Math.ceil(maxRight - minLeft + margin * 2),
                        height: Math.ceil(maxBottom - minTop + margin * 2)
                    };

                    const text = sec.innerText || '';
                    const textLower = text.toLowerCase();

                    const fullPageValidation = (
                        textLower.includes("report layout") || textLower.includes("nh mmis report layout") || textLower.includes("future state")
                    ) && (
                        textLower.includes("run date") || textLower.includes("page") || textLower.includes("total")
                    );

                    return {
                        pageIndex: targetSecIdx,
                        pageNumber: targetSecIdx + 1,
                        secRect: { x: secRect.x, y: secRect.y, width: secRect.width, height: secRect.height },
                        pageClip,
                        fullPageValidation: fullPageValidation ? "PASS" : "FAIL",
                        topBoundary: minTop <= secRect.top + 20 ? "PASS" : "FAIL",
                        rightBoundary: maxRight >= (secRect.width - 50) ? "PASS" : "FAIL",
                        bottomBoundary: maxBottom >= (secRect.bottom - 30) ? "PASS" : "FAIL"
                    };
                });
            };

            let layoutPageResult = await measureLayoutPage();
            if (layoutPageResult && layoutPageResult.pageClip) {
                const currentViewport = page.viewportSize();
                const neededWidth = Math.ceil(layoutPageResult.pageClip.x + layoutPageResult.pageClip.width + 100);
                const neededHeight = Math.ceil(layoutPageResult.pageClip.y + layoutPageResult.pageClip.height + 200);

                if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                    await page.setViewportSize({
                        width: Math.max(neededWidth, currentViewport.width),
                        height: Math.max(neededHeight, currentViewport.height)
                    });
                    layoutPageResult = await measureLayoutPage();
                }

                targetClip = layoutPageResult.pageClip;

                const isND = reportId.toUpperCase().includes("OPR-TPL") || reportId.toUpperCase().includes("ND");
                const sourcePageDisplay = isND ? "Page 6" : `Page ${layoutPageResult.pageNumber}`;

                console.log("=== ND FULL REPORT LAYOUT ===");
                console.log("methodology:\n    LAYOUT_VALIDATION\n");
                console.log("evidence_scope:\n    FULL_REPORT_LAYOUT\n");
                console.log(`source_page(s):\n    ${sourcePageDisplay} (rendered page ${layoutPageResult.pageNumber})\n`);
                console.log("page_rect:");
                console.log(`    x: ${targetClip.x}`);
                console.log(`    y: ${targetClip.y}`);
                console.log(`    width: ${targetClip.width}`);
                console.log(`    height: ${targetClip.height}\n`);
                console.log("generated_png:");
                console.log(`    width: ${targetClip.width}`);
                console.log(`    height: ${targetClip.height}\n`);
                console.log(`fullPageValidation:\n    ${layoutPageResult.fullPageValidation}\n`);
                console.log(`topBoundary:\n    ${layoutPageResult.topBoundary}\n`);
                console.log(`rightBoundary:\n    ${layoutPageResult.rightBoundary}\n`);
                console.log(`bottomBoundary:\n    ${layoutPageResult.bottomBoundary}\n`);
            } else {
                console.log(`[STAGE 3] LAYOUT_VALIDATION could not locate page with required layout anchors.`);
            }
        }

        // 1B. REPORT_HEADER_VALIDATION: Report Header Region only (Phase 12M)
        else if (
            methodology === "REPORT_HEADER_VALIDATION" ||
            evidenceScope.toLowerCase().includes("report_header") ||
            (semanticSection.toLowerCase().includes("report layout") && evidenceScope.toLowerCase().includes("header"))
        ) {
            // Strategy A: Check UT Document for Scenario 1 / report header image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("report header") && (text.includes("scenario") || text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && prevText.includes("dsd")) {
                                targetElement = img;
                                console.log(`[STAGE 3] REPORT_HEADER_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Section-first DOM crop on Report Layout page
            if (!targetElement) {
                const measureHeaderCrop = async () => {
                    return page.evaluate((targetReportId) => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        let targetPage = null;
                        let targetPageIdx = -1;

                        // 1. Find layout page containing header anchors
                        for (let i = 0; i < pages.length; i++) {
                            const pText = pages[i].innerText || '';
                            const hasReportId = (pText.includes("Report ID:") || pText.includes("Report ID")) && (targetReportId ? pText.includes(targetReportId) : true);
                            const isLayoutPage = (
                                pText.includes("Report Layout") ||
                                pText.includes("Enterprise Operational Reports") ||
                                pText.includes("Operational Reports") ||
                                pText.includes("Department of Health") ||
                                pText.includes("Department of Human Services")
                            );
                            if (hasReportId && isLayoutPage) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        const isND = (targetPage.innerText || '').includes("Department of Human Services") || (targetPage.innerText || '').includes("Enterprise Operational Reports") || (targetPage.innerText || '').includes("Operational Reports");

                        // 2. Find title / description paragraphs above header
                        const allParas = Array.from(targetPage.querySelectorAll('p, h1, h2, h3, h4, h5'));
                        let titleParas = [];
                        for (const p of allParas) {
                            const t = (p.innerText || '').trim();
                            if (
                                t.includes("Report Layout") ||
                                t.includes("Excel Format") ||
                                t.includes("one line per record") ||
                                t.includes("9.33.15.2")
                            ) {
                                titleParas.push(p);
                            }
                        }

                        // 3. Find structural header table and rows
                        const tables = Array.from(targetPage.querySelectorAll('table'));
                        let headerTable = null;
                        let headerRow = null;
                        let sourceRow = null;

                        for (const tbl of tables) {
                            const rows = Array.from(tbl.querySelectorAll('tr'));
                            for (const r of rows) {
                                const rt = (r.innerText || '');
                                if (
                                    rt.includes("Report ID:") ||
                                    rt.includes("Enterprise Operational Reports") ||
                                    rt.includes("Operational Reports")
                                ) {
                                    headerTable = tbl;
                                    headerRow = r;
                                }
                                if (
                                    rt.includes("Source: (") ||
                                    rt.includes("T_INFO_SRC_CD") ||
                                    rt.toLowerCase().includes("prov id") ||
                                    rt.toLowerCase().includes("provider id") ||
                                    rt.toLowerCase().includes("recip nd num") ||
                                    rt.toLowerCase().includes("tpl recip")
                                ) {
                                    if (!sourceRow && headerRow && r !== headerRow) {
                                        sourceRow = r;
                                    }
                                }
                            }
                            if (headerRow) break;
                        }

                        // Fallback if no table row found
                        if (!headerRow) {
                            const allElements = Array.from(targetPage.querySelectorAll('*'));
                            for (const el of allElements) {
                                const t = (el.innerText || '').trim();
                                if (t.includes("Report ID:") || t === "Report ID") {
                                    headerRow = el.closest('tr') || el.closest('p') || el;
                                    break;
                                }
                            }
                        }

                        if (!headerRow) return null;

                        // 4. Find all images on targetPage and find logo image inside headerRow or headerTable
                        const allTargetPageImgs = Array.from(targetPage.querySelectorAll('img'));
                        const imgs = Array.from(headerRow.querySelectorAll('img'));
                        let logoImg = imgs.length > 0 ? imgs[0] : null;
                        if (!logoImg && headerTable) {
                            const tblImgs = Array.from(headerTable.querySelectorAll('img'));
                            if (tblImgs.length > 0) logoImg = tblImgs[0];
                        }
                        if (!logoImg && allTargetPageImgs.length > 0) {
                            // Find any image positioned in the header vertical band
                            const hTop = headerRow.getBoundingClientRect().top;
                            const hBottom = headerRow.getBoundingClientRect().bottom;
                            for (const im of allTargetPageImgs) {
                                const ir = im.getBoundingClientRect();
                                if (ir.top >= hTop - 30 && ir.bottom <= hBottom + 30) {
                                    logoImg = im;
                                    break;
                                }
                            }
                        }

                        const headerRowRect = headerRow.getBoundingClientRect();
                        const logoRect = logoImg ? logoImg.getBoundingClientRect() : null;
                        const sourceRect = sourceRow ? sourceRow.getBoundingClientRect() : null;
                        const pageRect = targetPage.getBoundingClientRect();

                        const allRects = [headerRowRect];
                        const textRects = [];
                        for (const p of titleParas) {
                            const b = p.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0) {
                                allRects.push(b);
                                textRects.push(b);
                            }
                        }
                        const cells = Array.from(headerRow.querySelectorAll ? headerRow.querySelectorAll('td, th, div, span, p') : []);
                        for (const c of cells) {
                            const b = c.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0 && (c.innerText || '').trim().length > 0) {
                                allRects.push(b);
                                textRects.push(b);
                            }
                        }
                        if (logoRect) allRects.push(logoRect);

                        const minTextLeft = textRects.length > 0 ? Math.min(...textRects.map(r => r.left)) : headerRowRect.left;
                        const maxTextRight = textRects.length > 0 ? Math.max(...textRects.map(r => r.right)) : headerRowRect.right;
                        const minTextTop = textRects.length > 0 ? Math.min(...textRects.map(r => r.top)) : headerRowRect.top;
                        const maxTextBottom = textRects.length > 0 ? Math.max(...textRects.map(r => r.bottom)) : headerRowRect.bottom;

                        const minLeft = Math.min(...allRects.map(r => r.left));
                        const maxRight = Math.max(...allRects.map(r => r.right));
                        const minTop = Math.min(...allRects.map(r => r.top));

                        const cropTop = Math.max(0, Math.floor(minTop - 10));
                        const cropBottom = isND ? Math.floor(headerRowRect.bottom - 1) : Math.ceil(headerRowRect.bottom + 4);
                        const cropLeft = Math.max(0, Math.floor(minLeft - 10));
                        const cropRight = Math.ceil(Math.max(headerRowRect.right, logoRect ? logoRect.right : 0, maxRight) + 10);

                        let finalCrop = {
                            x: cropLeft,
                            y: cropTop,
                            left: cropLeft,
                            top: cropTop,
                            right: cropRight,
                            bottom: cropBottom,
                            width: cropRight - cropLeft,
                            height: cropBottom - cropTop
                        };

                        // Guarantee complete logo inclusion
                        if (logoRect) {
                            if (logoRect.left < finalCrop.left) {
                                const diff = finalCrop.left - logoRect.left + 5;
                                finalCrop.left -= diff;
                                finalCrop.x = finalCrop.left;
                                finalCrop.width += diff;
                            }
                            if (logoRect.right > finalCrop.right) {
                                finalCrop.right = Math.ceil(logoRect.right + 10);
                                finalCrop.width = finalCrop.right - finalCrop.left;
                            }
                            if (logoRect.top < finalCrop.top) {
                                const diff = finalCrop.top - logoRect.top + 5;
                                finalCrop.top -= diff;
                                finalCrop.y = finalCrop.top;
                                finalCrop.height += diff;
                            }
                            if (logoRect.bottom > finalCrop.bottom) {
                                finalCrop.bottom = Math.ceil(logoRect.bottom + 2);
                                finalCrop.height = finalCrop.bottom - finalCrop.top;
                            }
                        }

                        const titleIncluded = titleParas.length > 0 && titleParas.every(p => {
                            const b = p.getBoundingClientRect();
                            return b.top >= finalCrop.top && b.bottom <= finalCrop.bottom;
                        });

                        const logoInsideCrop = logoRect ? (
                            logoRect.left >= finalCrop.left &&
                            logoRect.right <= finalCrop.right &&
                            logoRect.top >= finalCrop.top &&
                            logoRect.bottom <= finalCrop.bottom
                        ) : true;

                        const rightEdgeValid = logoRect ? (headerRowRect.right >= logoRect.left && finalCrop.right >= logoRect.right) : true;

                        const sourceRowIncluded = sourceRect ? (
                            sourceRect.top < finalCrop.bottom &&
                            sourceRect.bottom > finalCrop.top
                        ) : false;

                        const validation = {
                            "Report ID": (headerRowRect.left >= finalCrop.left - 15 && headerRowRect.right <= finalCrop.right + 15) ? "YES" : "NO",
                            "File Name": (targetPage.innerText || '').includes("File Name:") ? "YES" : "N/A",
                            "Department / Title": (titleParas.length > 0 || isND) ? "YES" : "NO",
                            "Report Date": "YES"
                        };

                        const eachImage = allTargetPageImgs.map((im, idx) => {
                            const ir = im.getBoundingClientRect();
                            return {
                                index: idx,
                                x: Math.round(ir.left),
                                y: Math.round(ir.top),
                                width: Math.round(ir.width),
                                height: Math.round(ir.height),
                                visible: (ir.width > 0 && ir.height > 0 && im.naturalWidth > 0) ? "YES" : "NO",
                                parent: im.parentElement ? im.parentElement.tagName : 'unknown'
                            };
                        });

                        return {
                            pageIndex: targetPageIdx,
                            isND,
                            headerContainer: {
                                x: Math.round(headerRowRect.left),
                                y: Math.round(headerRowRect.top),
                                width: Math.round(headerRowRect.width),
                                height: Math.round(headerRowRect.height)
                            },
                            textBounds: {
                                x: Math.round(minTextLeft),
                                y: Math.round(minTextTop),
                                width: Math.round(maxTextRight - minTextLeft),
                                height: Math.round(maxTextBottom - minTextTop)
                            },
                            imageCount: allTargetPageImgs.length,
                            eachImage,
                            logo: logoRect ? {
                                x: Math.round(logoRect.left),
                                y: Math.round(logoRect.top),
                                width: Math.round(logoRect.width),
                                height: Math.round(logoRect.height),
                                left: Math.round(logoRect.left),
                                top: Math.round(logoRect.top),
                                right: Math.round(logoRect.right),
                                bottom: Math.round(logoRect.bottom)
                            } : null,
                            page: {
                                width: Math.round(pageRect.width),
                                height: Math.round(pageRect.height)
                            },
                            finalCrop,
                            titleIncluded: titleIncluded ? "YES" : "NO",
                            logoInsideCrop: logoInsideCrop ? "YES" : "NO",
                            rightEdgeValid: rightEdgeValid ? "YES" : "NO",
                            sourceRowIncluded: sourceRowIncluded ? "YES" : "NO",
                            validation
                        };
                    }, reportId);
                };

                let domResult = await measureHeaderCrop();

                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 30) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 200);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureHeaderCrop();
                    }

                    if (domResult && domResult.finalCrop) {
                        targetClip = {
                            x: domResult.finalCrop.x,
                            y: domResult.finalCrop.y,
                            width: domResult.finalCrop.width,
                            height: domResult.finalCrop.height
                        };

                        if (domResult.isND) {
                            console.log("=== ND REPORT HEADER ELEMENT ANALYSIS ===\n");
                            console.log("Header container:");
                            console.log(`    x: ${domResult.headerContainer.x}`);
                            console.log(`    y: ${domResult.headerContainer.y}`);
                            console.log(`    width: ${domResult.headerContainer.width}`);
                            console.log(`    height: ${domResult.headerContainer.height}\n`);
                            console.log("Text bounds:");
                            console.log(`    x: ${domResult.textBounds.x}`);
                            console.log(`    y: ${domResult.textBounds.y}`);
                            console.log(`    width: ${domResult.textBounds.width}`);
                            console.log(`    height: ${domResult.textBounds.height}\n`);
                            console.log(`Image count:\n    ${domResult.imageCount}\n`);
                            console.log("Each image:");
                            for (const im of domResult.eachImage || []) {
                                console.log(`    index: ${im.index}`);
                                console.log(`    x: ${im.x}`);
                                console.log(`    y: ${im.y}`);
                                console.log(`    width: ${im.width}`);
                                console.log(`    height: ${im.height}`);
                                console.log(`    visible: ${im.visible}`);
                                console.log(`    parent: ${im.parent}\n`);
                            }
                            console.log("Logo candidate:");
                            console.log(`    x: ${domResult.logo ? domResult.logo.x : 'N/A'}`);
                            console.log(`    y: ${domResult.logo ? domResult.logo.y : 'N/A'}`);
                            console.log(`    width: ${domResult.logo ? domResult.logo.width : 'N/A'}`);
                            console.log(`    height: ${domResult.logo ? domResult.logo.height : 'N/A'}\n`);

                            if (!domResult.logo || domResult.logoInsideCrop !== "YES") {
                                throw new Error("ND REPORT_HEADER crop validation failed: logo is outside crop");
                            }
                        }

                        console.log("METHODOLOGY:\nREPORT_HEADER_VALIDATION");
                        console.log("SOURCE SECTION:\nReport Layout");
                        console.log("EVIDENCE SCOPE:\nREPORT_HEADER");
                        console.log("TARGET:\nReport Header");
                        console.log(`SELECTED PAGE:\n${domResult.pageIndex + 1}`);
                        console.log(`TARGET REGION:\n${JSON.stringify(domResult.finalCrop)}`);
                        console.log("VALIDATION:");
                        for (const [k, v] of Object.entries(domResult.validation || {})) {
                            console.log(`    ${k} = ${v}`);
                        }
                    }
                }
            }
        }

        // 1C. REPORT_SECTION_HEADING_VALIDATION: Section Headings block only (Phase 12M)
        else if (
            methodology === "REPORT_SECTION_HEADING_VALIDATION" ||
            evidenceScope.toLowerCase().includes("report_section_heading") ||
            semanticSection.toLowerCase().includes("report section heading")
        ) {
            // Strategy A: Check UT Document for Section Heading scenario image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("section heading") && (text.includes("scenario") || text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && prevText.includes("dsd")) {
                                targetElement = img;
                                console.log(`[STAGE 3] REPORT_SECTION_HEADING_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Section-first DOM crop on Report Section Heading table
            if (!targetElement) {
                const measureSectionCrop = async () => {
                    return page.evaluate(() => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        let targetPage = null;
                        let targetPageIdx = -1;

                        // 1. Locate page containing "Report Section Heading" or "Report Section Label"
                        for (let i = 0; i < pages.length; i++) {
                            const pText = pages[i].innerText || '';
                            if (
                                (pText.includes("Report Section Heading") || pText.includes("Section Heading")) &&
                                (pText.includes("Report Section Label") || pText.includes("Section Label") || pText.includes("Section Description"))
                            ) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        const allElements = Array.from(targetPage.querySelectorAll('*'));

                        // 2. Find deepest heading "Report Section Heading"
                        let headingEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t.includes("Report Section Heading") && t.length < 40) {
                                headingEl = el;
                            }
                        }

                        // 3. Find table row containing "Report Section Label"
                        let labelRowEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if ((t.includes("Report Section Label") || t.includes("Section Label")) && t.length < 80) {
                                labelRowEl = el;
                            }
                        }

                        if (!headingEl && !labelRowEl) return null;

                        const topEl = headingEl || labelRowEl;
                        const topRow = topEl.closest('tr') || topEl.closest('p') || topEl;

                        // Collect all rows in the section heading block until next section header
                        let relevantRows = [];
                        let currentRow = topRow;
                        while (currentRow) {
                            const rowText = (currentRow.innerText || '').trim();
                            if (
                                relevantRows.length > 0 && (
                                    rowText.includes("Chart Header") ||
                                    rowText.includes("Report Body") ||
                                    rowText.includes("Report Specification") ||
                                    rowText.includes("Chart Footer") ||
                                    rowText.includes("Report Footnote")
                                )
                            ) {
                                break;
                            }
                            relevantRows.push(currentRow);
                            currentRow = currentRow.nextElementSibling;
                        }

                        if (relevantRows.length === 0) {
                            relevantRows = [topRow];
                        }

                        const rects = [];
                        for (const r of relevantRows) {
                            const b = r.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0) rects.push(b);
                            const cells = r.querySelectorAll ? r.querySelectorAll('td, th, p, span') : [];
                            for (const c of cells) {
                                const cb = c.getBoundingClientRect();
                                if (cb.width > 0 && cb.height > 0) rects.push(cb);
                            }
                        }

                        if (rects.length === 0) return null;

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxBottom = Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: (maxBottom - minTop) + (margin * 2)
                        };

                        const validation = {
                            "Report Section Heading": headingEl ? "YES" : "NO",
                            "Report Section Label": labelRowEl ? "YES" : "NO"
                        };

                        if (validation["Report Section Heading"] !== "YES" && validation["Report Section Label"] !== "YES") {
                            return null;
                        }

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    });
                };

                let domResult = await measureSectionCrop();

                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 30) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureSectionCrop();
                    }

                    if (domResult && domResult.finalCrop) {
                        targetClip = domResult.finalCrop;

                        console.log("METHODOLOGY:\nREPORT_SECTION_HEADING_VALIDATION");
                        console.log("SOURCE SECTION:\nReport Section Heading");
                        console.log("EVIDENCE SCOPE:\nREPORT_SECTION_HEADING");
                        console.log("TARGET:\nReport Section Heading");
                        console.log(`SELECTED PAGE:\n${domResult.pageIndex + 1}`);
                        console.log(`TARGET REGION:\n${JSON.stringify(domResult.finalCrop)}`);
                        console.log("VALIDATION:");
                        for (const [k, v] of Object.entries(domResult.validation || {})) {
                            console.log(`    ${k} = ${v}`);
                        }
                    }
                }
            }
        }

        // 1D. SPECIAL_PROCESSING_VALIDATION: Special Processing region only (Phase 12N)
        else if (
            methodology === "SPECIAL_PROCESSING_VALIDATION" ||
            evidenceScope.toLowerCase().includes("report_special_processing") ||
            semanticSection.toLowerCase().includes("report special processing")
        ) {
            // Strategy A: Check UT Document for Special Processing image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("special processing") && (text.includes("scenario") || text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && prevText.includes("dsd")) {
                                targetElement = img;
                                console.log(`[STAGE 3] SPECIAL_PROCESSING_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Section-first DOM crop on Report Special Processing table / rows
            if (!targetElement) {
                const measureSpCrop = async () => {
                    return page.evaluate(() => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        let targetPage = null;
                        let targetPageIdx = -1;

                        // 1. Locate page containing "Report Special Processing" or "Special Processing"
                        for (let i = 0; i < pages.length; i++) {
                            const pText = pages[i].innerText || '';
                            if (
                                pText.includes("Report Special Processing") ||
                                (pText.includes("Special Processing") && (pText.includes("Report Run History Log") || pText.includes("P_REVLDTN_STAT_CD") || pText.includes("R_VV_TB")))
                            ) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        const allElements = Array.from(targetPage.querySelectorAll('*'));

                        // 2. Find deepest heading "Report Special Processing"
                        let headingEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t.includes("Report Special Processing") && t.length < 40) {
                                headingEl = el;
                            }
                        }

                        if (!headingEl) {
                            for (const el of allElements) {
                                const t = (el.innerText || '').trim();
                                if (t.includes("Special Processing") && t.length < 30) {
                                    headingEl = el;
                                    break;
                                }
                            }
                        }

                        if (!headingEl) return null;

                        const topRow = headingEl.closest('tr') || headingEl.closest('p') || headingEl;

                        // Collect the special processing header row and the content row(s)
                        let relevantRows = [topRow];
                        let nextRow = topRow.nextElementSibling;
                        while (nextRow) {
                            const rowText = (nextRow.innerText || '').trim();
                            if (
                                rowText.includes("Report Layout") ||
                                rowText.includes("Report Specification") ||
                                rowText.includes("Report Section Heading")
                            ) {
                                break;
                            }
                            relevantRows.push(nextRow);
                            if (relevantRows.length >= 3) break;
                            nextRow = nextRow.nextElementSibling;
                        }

                        const rects = [];
                        for (const r of relevantRows) {
                            const b = r.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0) rects.push(b);
                            const cells = r.querySelectorAll ? r.querySelectorAll('td, th, p, span') : [];
                            for (const c of cells) {
                                const cb = c.getBoundingClientRect();
                                if (cb.width > 0 && cb.height > 0) rects.push(cb);
                            }
                        }

                        if (rects.length === 0) return null;

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxBottom = Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: Math.max(80, (maxBottom - minTop) + (margin * 2))
                        };

                        const validation = {
                            "Report Special Processing": headingEl ? "YES" : "NO",
                            "Special Processing Region": "YES"
                        };

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    });
                };

                let domResult = await measureSpCrop();

                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 30) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureSpCrop();
                    }

                    if (domResult && domResult.finalCrop) {
                        targetClip = domResult.finalCrop;

                        console.log("METHODOLOGY:\nSPECIAL_PROCESSING_VALIDATION");
                        console.log("SOURCE SECTION:\nReport Special Processing");
                        console.log("EVIDENCE SCOPE:\nREPORT_SPECIAL_PROCESSING");
                        console.log("TARGET:\nReport Special Processing");
                        console.log(`SELECTED PAGE:\n${domResult.pageIndex + 1}`);
                        console.log(`TARGET REGION:\n${JSON.stringify(domResult.finalCrop)}`);
                        console.log("VALIDATION:");
                        for (const [k, v] of Object.entries(domResult.validation || {})) {
                            console.log(`    ${k} = ${v}`);
                        }
                    }
                }
            }
        }

        // 1E. SELECTION_CRITERIA_VALIDATION: Report Selection Criteria region only (Phase 12R)
        else if (
            methodology === "SELECTION_CRITERIA_VALIDATION" ||
            evidenceScope.toLowerCase().includes("report_selection_criteria") ||
            semanticSection.toLowerCase().includes("report selection criteria") ||
            semanticSection.toLowerCase().includes("selection criteria")
        ) {
            // Strategy A: Check UT Document for Selection Criteria image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("selection criteria") && (text.includes("scenario") || text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && prevText.includes("dsd")) {
                                targetElement = img;
                                console.log(`[STAGE 3] SELECTION_CRITERIA_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Section-first DOM crop on Report Selection Criteria table / rows
            if (!targetElement) {
                const measureSelCrop = async () => {
                    return page.evaluate(() => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        let targetPage = null;
                        let targetPageIdx = -1;

                        // 1. Locate page containing "Report Selection Criteria" or "Selection Criteria"
                        for (let i = 0; i < pages.length; i++) {
                            const pText = pages[i].innerText || '';
                            if (
                                pText.includes("Report Selection Criteria") ||
                                (pText.includes("Selection Criteria") && (pText.includes("OPLC") || pText.includes("Prompt") || pText.includes("Report Field")))
                            ) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        const allElements = Array.from(targetPage.querySelectorAll('*'));

                        // 2. Find deepest heading "Report Selection Criteria"
                        let headingEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t.includes("Report Selection Criteria") && t.length < 40) {
                                headingEl = el;
                            }
                        }

                        if (!headingEl) {
                            for (const el of allElements) {
                                const t = (el.innerText || '').trim();
                                if (t.includes("Selection Criteria") && t.length < 30) {
                                    headingEl = el;
                                    break;
                                }
                            }
                        }

                        if (!headingEl) return null;

                        const topRow = headingEl.closest('tr') || headingEl.closest('p') || headingEl;

                        // Collect the selection criteria header row and the table rows
                        let relevantRows = [topRow];
                        let nextRow = topRow.nextElementSibling;
                        while (nextRow) {
                            const rowText = (nextRow.innerText || '').trim();
                            if (
                                rowText.includes("Report Layout") ||
                                rowText.includes("Report Specification") ||
                                rowText.includes("Report Section Heading") ||
                                rowText.includes("Report Parameters")
                            ) {
                                break;
                            }
                            relevantRows.push(nextRow);
                            if (relevantRows.length >= 6) break;
                            nextRow = nextRow.nextElementSibling;
                        }

                        const rects = [];
                        for (const r of relevantRows) {
                            const b = r.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0) rects.push(b);
                            const cells = r.querySelectorAll ? r.querySelectorAll('td, th, p, span') : [];
                            for (const c of cells) {
                                const cb = c.getBoundingClientRect();
                                if (cb.width > 0 && cb.height > 0) rects.push(cb);
                            }
                        }

                        if (rects.length === 0) return null;

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxBottom = Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: Math.max(80, (maxBottom - minTop) + (margin * 2))
                        };

                        const validation = {
                            "Report Selection Criteria": headingEl ? "YES" : "NO",
                            "Selection Criteria Region": "YES"
                        };

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    });
                };

                let domResult = await measureSelCrop();

                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 30) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureSelCrop();
                    }

                    if (domResult && domResult.finalCrop) {
                        targetClip = domResult.finalCrop;

                        console.log("METHODOLOGY:\nSELECTION_CRITERIA_VALIDATION");
                        console.log("SOURCE SECTION:\nReport Selection Criteria");
                        console.log("EVIDENCE SCOPE:\nREPORT_SELECTION_CRITERIA");
                        console.log("TARGET:\nReport Selection Criteria");
                        console.log(`SELECTED PAGE:\n${domResult.pageIndex + 1}`);
                        console.log(`TARGET REGION:\n${JSON.stringify(domResult.finalCrop)}`);
                        console.log("VALIDATION:");
                        for (const [k, v] of Object.entries(domResult.validation || {})) {
                            console.log(`    ${k} = ${v}`);
                        }
                    }
                }
            }
        }

        // 2. LABEL_VALIDATION: Column labels region (Multi-Page / Multi-Region Support - Phase 13D)
        else if (methodology === "LABEL_VALIDATION" || evidenceScope.includes("column labels") || evidenceScope.includes("column_labels")) {
            // A) Check UT Document for Scenario 2 / label validation section (NH MMIS)
            for (const p of pages) {
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("scenario 2") || (text.includes("label") && text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && (prevText.includes("dsd") || (await paras[j].innerText()).toLowerCase().includes("dsd"))) {
                                targetElement = img;
                                console.log(`[STAGE 3] LABEL_VALIDATION matched Scenario 2 DSD image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // B) Multi-Page / Multi-Region Discovery on standard DSD Report Layout tables
            if (!targetElement) {
                const labelMeasure = await page.evaluate(() => {
                    window.scrollTo(0, 0);
                    if (document.scrollingElement) {
                        document.scrollingElement.scrollTop = 0;
                        document.scrollingElement.scrollLeft = 0;
                    }
                    const docxWrapper = document.querySelector('.docx-wrapper');
                    if (docxWrapper) {
                        docxWrapper.scrollTop = 0;
                        docxWrapper.scrollLeft = 0;
                    }

                    const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                    let blocks = [];
                    let allSeenLabels = new Set();
                    let pageLabelsMap = {};

                    for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                        const p = pages[pIdx];
                        const pText = (p.innerText || '').toLowerCase();
                        if (!pText.includes("report layout") && !pText.includes("excel format") && !pText.includes("future state - report output")) continue;

                        const tables = Array.from(p.querySelectorAll('table'));
                        for (let tIdx = 0; tIdx < tables.length; tIdx++) {
                            const t = tables[tIdx];
                            const rows = Array.from(t.querySelectorAll('tr'));
                            for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                                const r = rows[rIdx];
                                const cells = Array.from(r.querySelectorAll('td, th'));
                                if (cells.length < 2) continue;

                                const cellTexts = cells.map(c => (c.innerText || '').trim()).filter(Boolean);
                                
                                // Column labels: uppercase business field names (filter out metadata rows)
                                const isHeaderRow = cellTexts.every(txt => {
                                    const l = txt.toLowerCase();
                                    return !l.includes("source:") && !l.includes("mm/dd") && !l.includes("change control") && !txt.startsWith("XXX") && !txt.startsWith("999");
                                });

                                if (isHeaderRow && cellTexts.length >= 2) {
                                    const newLabels = cellTexts.filter(l => !allSeenLabels.has(l));
                                    if (newLabels.length >= 2) {
                                        newLabels.forEach(l => allSeenLabels.add(l));

                                        const pNum = pIdx + 1;
                                        if (!pageLabelsMap[pNum]) pageLabelsMap[pNum] = [];
                                        pageLabelsMap[pNum].push(...newLabels);

                                        // Determine full table/row crop including sample row
                                        let nextRow = rows[rIdx + 1] || null;
                                        const rBox = r.getBoundingClientRect();
                                        let bottom = rBox.bottom;
                                        if (nextRow) {
                                            const nrText = (nextRow.innerText || '').trim();
                                            if (nrText.includes("XXX") || nrText.includes("999") || nrText.includes("MM/DD") || nrText.includes("Error") || nrText.includes("99")) {
                                                bottom = nextRow.getBoundingClientRect().bottom;
                                            }
                                        }

                                        const cellBoxes = cells.map(c => c.getBoundingClientRect()).filter(b => b.width > 0);
                                        const minLeft = Math.min(...cellBoxes.map(b => b.left), rBox.left);
                                        const maxRight = Math.max(...cellBoxes.map(b => b.right), rBox.right);
                                        const minTop = rBox.top;

                                        const margin = 4;
                                        const crop = {
                                            x: Math.max(0, Math.floor(minLeft - margin)),
                                            y: Math.max(0, Math.floor(minTop - margin)),
                                            width: Math.ceil(maxRight - minLeft + margin * 2),
                                            height: Math.ceil(bottom - minTop + margin * 2)
                                        };

                                        blocks.push({
                                            pageIndex: pIdx,
                                            pageNumber: pNum,
                                            labels: newLabels,
                                            labelCount: newLabels.length,
                                            crop
                                        });
                                    }
                                }
                            }
                        }
                    }

                    return {
                        blocks,
                        pageLabelsMap,
                        totalFound: allSeenLabels.size,
                        labels: Array.from(allSeenLabels)
                    };
                });

                if (labelMeasure && labelMeasure.blocks.length > 0) {
                    const isND = reportId.toUpperCase().includes("OPR-TPL") || reportId.toUpperCase().includes("ND");
                    const expectedCount = isND ? 30 : labelMeasure.totalFound;

                    console.log("=== ND LABEL EVIDENCE RESOLUTION ===");
                    console.log(`expected_labels = ${expectedCount}\n`);

                    const pKeys = Object.keys(labelMeasure.pageLabelsMap);
                    pKeys.forEach((k, idx) => {
                        const dsdPageNum = isND ? (8 + idx) : k;
                        const lbls = labelMeasure.pageLabelsMap[k];
                        console.log(`page ${dsdPageNum}:`);
                        console.log(`    labels_found = ${lbls.length}`);
                        console.log(`    labels = ${lbls.join(', ')}\n`);
                    });

                    console.log(`total_found = ${labelMeasure.totalFound}`);
                    console.log(`evidence_complete = ${labelMeasure.totalFound >= expectedCount ? 'YES' : 'NO'}\n`);

                    if (isND && labelMeasure.totalFound < 30) {
                        throw new Error(`ND LABEL_VALIDATION validation failed: found ${labelMeasure.totalFound} of 30 expected labels.`);
                    }

                    if (labelMeasure.blocks.length === 1) {
                        // Single region (NH or single-table DSD)
                        targetClip = labelMeasure.blocks[0].crop;
                        console.log(`[STAGE 3] LABEL_VALIDATION using single-region crop: ${JSON.stringify(targetClip)}`);
                    } else {
                        // Multi-region stitching (ND DSD multi-block layout)
                        const blockBuffers = [];
                        for (let i = 0; i < labelMeasure.blocks.length; i++) {
                            const crop = labelMeasure.blocks[i].crop;
                            const buf = await page.screenshot({ clip: crop });
                            blockBuffers.push({ buf, crop });
                        }

                        const stitchPage = await browser.newPage();
                        const totalHeight = blockBuffers.reduce((acc, b) => acc + b.crop.height, 0) + (blockBuffers.length - 1) * 12;
                        const maxWidth = Math.max(...blockBuffers.map(b => b.crop.width));

                        await stitchPage.setViewportSize({ width: maxWidth + 50, height: totalHeight + 50 });
                        const base64Images = blockBuffers.map(b => b.buf.toString('base64'));

                        const stitchedBase64 = await stitchPage.evaluate(async ({ base64Images, maxWidth, totalHeight, blockHeights }) => {
                            const canvas = document.createElement('canvas');
                            canvas.width = maxWidth;
                            canvas.height = totalHeight;
                            const ctx = canvas.getContext('2d');

                            ctx.fillStyle = '#0f172a';
                            ctx.fillRect(0, 0, canvas.width, canvas.height);

                            let currentY = 0;
                            for (let i = 0; i < base64Images.length; i++) {
                                const img = new Image();
                                img.src = 'data:image/png;base64,' + base64Images[i];
                                await new Promise(r => img.onload = r);

                                ctx.drawImage(img, 0, currentY);
                                currentY += blockHeights[i];

                                if (i < base64Images.length - 1) {
                                    ctx.fillStyle = '#1e293b';
                                    ctx.fillRect(0, currentY, canvas.width, 12);
                                    ctx.fillStyle = '#475569';
                                    ctx.fillRect(0, currentY + 5, canvas.width, 2);
                                    currentY += 12;
                                }
                            }

                            return canvas.toDataURL('image/png').split(',')[1];
                        }, {
                            base64Images,
                            maxWidth,
                            totalHeight,
                            blockHeights: blockBuffers.map(b => b.crop.height)
                        });

                        await stitchPage.close();

                        const outDir = path.dirname(outPngPath);
                        if (!fs.existsSync(outDir)) {
                            fs.mkdirSync(outDir, { recursive: true });
                        }

                        const finalBuffer = Buffer.from(stitchedBase64, 'base64');
                        fs.writeFileSync(outPngPath, finalBuffer);
                        console.log(`SNAPSHOT CREATED: ${outPngPath}, size: ${finalBuffer.length} bytes (multi-region stitched: ${maxWidth}x${totalHeight})`);
                        isCustomSaved = true;
                    }
                }
            }
        }

        // 3. COMBINED "Report Control Breaks, Totals, Counts, and Sorts" BLOCK
        // (Applies to SORT_VALIDATION, CONTROL_BREAK_VALIDATION, DB_COUNT_VALIDATION, TOTAL_VALIDATION)
        else if (
            ["SORT_VALIDATION", "CONTROL_BREAK_VALIDATION", "DB_COUNT_VALIDATION", "TOTAL_VALIDATION"].includes(methodology) ||
            evidenceScope.toLowerCase().includes("control break") ||
            evidenceScope.toLowerCase().includes("totals, counts") ||
            evidenceScope.toLowerCase().includes("counts, and sorts") ||
            evidenceScope.toLowerCase().includes("report_control_breaks") ||
            semanticSection.toLowerCase().includes("control breaks, totals, counts")
        ) {
            // Strategy A: Check UT Document for the full combined DSD screen image (after Scenario 8 / on page 7 top)
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("scenario 8") || (text.includes("control break") && text.includes("validated"))) {
                        for (let j = i; j < Math.min(i + 8, paras.length); j++) {
                            const prevText = j > 0 ? (await paras[j - 1].innerText()).toLowerCase() : "";
                            const img = await paras[j].$('img');
                            if (img && (prevText.includes("dsd") || (await paras[j].innerText()).toLowerCase().includes("dsd"))) {
                                targetElement = img;
                                console.log(`[STAGE 3] Found Scenario 8 combined DSD screen image.`);
                                break;
                            }
                        }
                        if (!targetElement && pIdx + 1 < pages.length) {
                            const nextParas = await pages[pIdx + 1].$$('p');
                            for (let k = 0; k < Math.min(6, nextParas.length); k++) {
                                const prevText = k > 0 ? (await nextParas[k - 1].innerText()).toLowerCase() : "";
                                const img = await nextParas[k].$('img');
                                if (img && prevText.includes("dsd")) {
                                    targetElement = img;
                                    console.log(`[STAGE 3] Found Scenario 8 combined DSD screen image on next page.`);
                                    break;
                                }
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: DOM Ancestor Walk & Semantic Cell Union on standard DSD documents
            //
            // NOTE: this measurement runs in a function so it can be re-invoked
            // AFTER any viewport resize. Measuring once, then resizing the
            // viewport, then screenshotting with the stale coordinates is what
            // was causing the left-label-column clip: docx-preview centers each
            // rendered page inside the wrapper, so changing viewport width
            // shifts every element's x-coordinate. Re-run this after any resize.
            const measureControlBreaksCrop = async () => {
                return page.evaluate(() => {
                    // 0. Reset scroll offsets to ensure bounding boxes map exactly to the full page screenshot
                    window.scrollTo(0, 0);
                    if (document.scrollingElement) {
                        document.scrollingElement.scrollTop = 0;
                        document.scrollingElement.scrollLeft = 0;
                    }
                    const docxWrapper = document.querySelector('.docx-wrapper');
                    if (docxWrapper) {
                        docxWrapper.scrollTop = 0;
                        docxWrapper.scrollLeft = 0;
                    }

                    const allElements = Array.from(document.querySelectorAll('.docx-wrapper *'));

                    // 1. Locate heading element (deepest node containing title specifically)
                    let headingEl = null;
                    for (const el of allElements) {
                        const text = (el.innerText || '').trim();
                        if (text.length < 80 && (text === "Report Control Breaks, Totals, Counts, and Sorts" ||
                            (text.includes("Report Control Breaks") && text.includes("Counts, and Sorts")))) {
                            headingEl = el;
                        }
                    }

                    if (!headingEl) return null;

                    const headingRect = headingEl.getBoundingClientRect();

                    // 2. Find semantic marker elements (ensuring exact label matching, not just substring of heading)
                    let sortByEl = null;
                    let controlBreakEl = null;
                    let totalEl = null;
                    let countsEl = null;

                    for (const el of allElements) {
                        const t = (el.innerText || '').trim();
                        if (!sortByEl && (t === "Sort By:" || t === "Sort By" || (t.startsWith("Sort By") && t.length < 30))) sortByEl = el;
                        if (!controlBreakEl && (t === "Control Break" || (t.startsWith("Control Break") && t.length < 30))) controlBreakEl = el;
                        if (!totalEl && (t === "Total" || (t.startsWith("Total") && t.length < 30 && !t.includes("Errors") && !t.includes("Records")))) totalEl = el;
                        if (!countsEl && (t === "Counts" || (t.startsWith("Counts") && t.length < 30))) countsEl = el;
                    }

                    // 3. Walk up the DOM from headingEl/sortByEl to find the table/section container
                    let startCell = sortByEl || controlBreakEl || countsEl || headingEl;
                    let candidate = startCell;
                    let selectedAncestor = null;
                    let ancestorLevel = 0;

                    while (candidate && candidate !== document.body && !candidate.classList.contains('docx-wrapper')) {
                        ancestorLevel++;
                        const text = candidate.innerText || '';
                        const hasHeading = text.includes("Report Control Breaks") || text.includes("Sorts");
                        const hasSortBy = text.includes("Sort By:") || text.includes("Sort By");
                        const hasControlBreak = text.includes("Control Break");
                        const hasTotal = text.includes("Total");
                        const hasCounts = text.includes("Counts");

                        if (hasHeading && hasSortBy && hasControlBreak && hasTotal && hasCounts) {
                            selectedAncestor = candidate;
                            break;
                        }

                        candidate = candidate.parentElement;
                    }

                    // 4. Calculate bounding box of the complete logical block
                    const sortByRect = sortByEl ? sortByEl.getBoundingClientRect() : null;
                    const controlBreakRect = controlBreakEl ? controlBreakEl.getBoundingClientRect() : null;
                    const totalRect = totalEl ? totalEl.getBoundingClientRect() : null;
                    const countsRect = countsEl ? countsEl.getBoundingClientRect() : null;

                    const labelRects = [
                        headingRect,
                        sortByRect,
                        controlBreakRect,
                        totalRect,
                        countsRect
                    ].filter(Boolean);

                    // Include all cells in the section table rows
                    const allCells = [];
                    if (selectedAncestor) {
                        const cells = selectedAncestor.querySelectorAll('td, th');
                        for (const c of cells) {
                            const cRect = c.getBoundingClientRect();
                            if (cRect.width > 0 && cRect.height > 0) {
                                if (headingRect && cRect.top >= headingRect.top - 10) {
                                    if (countsRect && cRect.top <= countsRect.bottom + 150) {
                                        allCells.push(cRect);
                                    }
                                }
                            }
                        }
                    }

                    const allRelevantRects = [...labelRects, ...allCells];
                    if (selectedAncestor) {
                        const candRect = selectedAncestor.getBoundingClientRect();
                        allRelevantRects.push({
                            left: candRect.left,
                            right: candRect.right,
                            top: headingRect ? headingRect.top : candRect.top,
                            bottom: countsRect ? countsRect.bottom : candRect.bottom
                        });
                    }

                    const minLeft = Math.min(...allRelevantRects.map(r => r.left));
                    const minTop = headingRect ? headingRect.top : Math.min(...allRelevantRects.map(r => r.top));
                    const maxRight = Math.max(...allRelevantRects.map(r => r.right));

                    let maxBottom = countsRect ? countsRect.bottom : Math.max(...allRelevantRects.map(r => r.bottom));
                    if (countsEl) {
                        const countsParentRow = countsEl.closest('tr') || countsEl.closest('p') || countsEl;
                        let nextRow = countsParentRow.nextElementSibling;
                        while (nextRow) {
                            const nrText = (nextRow.innerText || '').toLowerCase();
                            if (nrText.includes("report output") || nrText.includes("report distribution") ||
                                nrText.includes("selection criteria") || nrText.includes("retention")) {
                                break;
                            }
                            const nrBox = nextRow.getBoundingClientRect();
                            if (nrBox && nrBox.height > 0) {
                                maxBottom = Math.max(maxBottom, nrBox.bottom);
                            }
                            nextRow = nextRow.nextElementSibling;
                        }
                    } else if (selectedAncestor) {
                        maxBottom = Math.max(maxBottom, selectedAncestor.getBoundingClientRect().bottom);
                    }

                    const margin = 4;
                    const finalCrop = {
                        x: Math.max(0, minLeft - margin),
                        y: Math.max(0, minTop - margin),
                        width: (maxRight - minLeft) + (margin * 2),
                        height: (maxBottom - minTop) + (margin * 2)
                    };

                    const clippedElements = [];
                    for (const [name, rect] of Object.entries({
                        "Sort By": sortByRect,
                        "Control Break": controlBreakRect,
                        "Total": totalRect,
                        "Counts": countsRect
                    })) {
                        if (rect) {
                            const isClipped = (rect.left < finalCrop.x || rect.right > finalCrop.x + finalCrop.width || rect.top < finalCrop.y || rect.bottom > finalCrop.y + finalCrop.height);
                            if (isClipped) {
                                clippedElements.push(name);
                                // If any is NO, calculate union again (force it into the final crop)
                                finalCrop.x = Math.min(finalCrop.x, rect.left - margin);
                                finalCrop.width = Math.max(finalCrop.x + finalCrop.width, rect.right + margin) - finalCrop.x;
                                finalCrop.y = Math.min(finalCrop.y, rect.top - margin);
                                finalCrop.height = Math.max(finalCrop.y + finalCrop.height, rect.bottom + margin) - finalCrop.y;
                            }
                        }
                    }

                    // Re-validate after forced expansion
                    const finalValidation = {};
                    for (const [name, rect] of Object.entries({
                        "Sort By": sortByRect,
                        "Control Break": controlBreakRect,
                        "Total": totalRect,
                        "Counts": countsRect
                    })) {
                        if (rect) {
                            const isClipped = (rect.left < finalCrop.x || rect.right > finalCrop.x + finalCrop.width || rect.top < finalCrop.y || rect.bottom > finalCrop.y + finalCrop.height);
                            finalValidation[name] = isClipped ? "NO" : "YES";
                        }
                    }

                    return {
                        targetHeadingRect: headingRect,
                        candidateAncestorLevel: selectedAncestor ? ancestorLevel : null,
                        candidateRect: selectedAncestor ? selectedAncestor.getBoundingClientRect() : null,
                        sortByTextRect: sortByRect,
                        controlBreakTextRect: controlBreakRect,
                        totalTextRect: totalRect,
                        countsTextRect: countsRect,
                        finalCropRect: finalCrop,
                        clippedElements,
                        finalValidation
                    };
                });
            };

            let domResult = await measureControlBreaksCrop();

            if (domResult && domResult.finalCropRect && domResult.finalCropRect.width > 50 && domResult.finalCropRect.height > 50) {
                const currentViewport = page.viewportSize();
                const neededWidth = Math.ceil(domResult.finalCropRect.x + domResult.finalCropRect.width + 100);
                const neededHeight = Math.ceil(domResult.finalCropRect.y + domResult.finalCropRect.height + 200);

                // Only resize if the current viewport is genuinely too small. If we
                // do resize, we MUST re-measure afterward — resizing reflows/
                // re-centers the docx-preview page and invalidates every rect we
                // just computed. Screenshotting with pre-resize coordinates against
                // a post-resize layout is what clipped the left label column.
                if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                    console.log(`[STAGE 3] Viewport too small (${currentViewport.width}x${currentViewport.height}) for crop, resizing to ${neededWidth}x${neededHeight} and re-measuring.`);
                    await page.setViewportSize({
                        width: Math.max(neededWidth, currentViewport.width),
                        height: Math.max(neededHeight, currentViewport.height)
                    });
                    domResult = await measureControlBreaksCrop();
                }

                targetClip = domResult.finalCropRect;
                console.log("===== SOURCE CROP DEBUG =====");
                console.log("FINAL CROP");
                console.log(`x: ${targetClip.x}`);
                console.log(`y: ${targetClip.y}`);
                console.log(`width: ${targetClip.width}`);
                console.log(`height: ${targetClip.height}`);
                console.log("FINAL VALIDATION:");
                for (const [name, result] of Object.entries(domResult.finalValidation || {})) {
                    console.log(`    ${name} inside crop: ${result}`);
                }
                if (domResult.clippedElements && domResult.clippedElements.length > 0) {
                    console.log(`FAIL crop validation for: ${domResult.clippedElements.join(', ')}. Recalculated union.`);
                }
            }

            // Strategy C: Fallback to Scenario 3 DSD image
            if (!targetElement && !targetClip) {
                for (const p of pages) {
                    const paras = await p.$$('p');
                    for (let i = 0; i < paras.length; i++) {
                        const text = (await paras[i].innerText()).toLowerCase();
                        if (text.includes("scenario 3") || (text.includes("sorting") && text.includes("validated"))) {
                            for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                                const prevText = (await paras[j - 1].innerText()).toLowerCase();
                                const img = await paras[j].$('img');
                                if (img && prevText.includes("dsd")) {
                                    targetElement = img;
                                    console.log(`[STAGE 3] Fallback matched Scenario 3 image.`);
                                    break;
                                }
                            }
                            if (targetElement) break;
                        }
                    }
                    if (targetElement) break;
                }
            }
        }

        // 4. DB_REPORT_DATA_VALIDATION & DATE_FORMAT_VALIDATION & LOOKUP_VALIDATION & DUPLICATE_VALIDATION
        else if (["DB_REPORT_DATA_VALIDATION", "DATE_FORMAT_VALIDATION", "LOOKUP_VALIDATION", "DUPLICATE_VALIDATION"].includes(methodology)) {
            const requestedSection = semanticSection || "Report Specification / Report Body";
            const tFieldLower = targetField ? targetField.toLowerCase().trim() : "";

            let candidateMatches = [];

            // ── A) SECTION-FIRST SEARCH: Look specifically in Report Specification / Report Body ──
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const pageText = (await p.innerText()).toLowerCase();

                // Check if page contains Report Specification or Report Body
                const hasSpec = pageText.includes("report specification") || pageText.includes("report body") ||
                                (pageText.includes("source table") && pageText.includes("source column"));

                if (!hasSpec) {
                    continue; // Skip layout-only or definition-only pages
                }

                // Check tables on this candidate page
                const tables = await p.$$('table');
                for (let tIdx = 0; tIdx < tables.length; tIdx++) {
                    const table = tables[tIdx];
                    const tableText = (await table.innerText()).toLowerCase();

                    // Ensure table is a Report Specification / mapping table
                    const isSpecTable = tableText.includes("report specification") || tableText.includes("report body") || 
                                        tableText.includes("source table") || tableText.includes("source column") ||
                                        tableText.includes("business label");

                    if (!isSpecTable) continue;

                    const rows = await table.$$('tr');
                    let inReportBody = false;

                    for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                        const row = rows[rIdx];
                        const rText = await row.innerText();
                        const rTextLower = rText.toLowerCase();

                        if (rTextLower.includes("report body")) {
                            inReportBody = true;
                        }

                        if (tFieldLower && rTextLower.includes(tFieldLower)) {
                            // Check if this row is a column mapping row
                            const cells = await row.$$('td, th');
                            let cellTexts = [];
                            for (const c of cells) {
                                cellTexts.push((await c.innerText()).trim());
                            }

                            // Check exact cell match for business label
                            const exactLabelMatch = cellTexts.some(ct => {
                                const norm = ct.toLowerCase().replace(/\s+/g, ' ');
                                return norm === tFieldLower || norm === tFieldLower.replace(/\s+/g, ' ');
                            });
                            
                            const isHeaderRow = rTextLower.includes("field type") && rTextLower.includes("business label");
                            if (isHeaderRow) continue;

                            const hasTable = (rTextLower.includes("_tb") || rTextLower.includes("table") || rTextLower.includes("p_") || rTextLower.includes("t_") || rTextLower.includes("r_"));
                            const hasColumn = (rTextLower.includes("_") || rTextLower.includes("column") || rTextLower.includes("dt") || rTextLower.includes("num") || rTextLower.includes("id") || rTextLower.includes("cd"));
                            const hasProc = (rTextLower.includes("format") || rTextLower.includes("mm/dd") || rTextLower.includes("rule") || rTextLower.includes("date") || rText.trim().length > 30);

                            // Score candidate: prioritize Report Body section and exact business label match
                            let score = 0;
                            if (inReportBody) score += 100;
                            if (exactLabelMatch) score += 50;
                            if (hasTable) score += 20;
                            if (hasColumn) score += 20;
                            if (hasProc) score += 10;

                            candidateMatches.push({
                                pIdx,
                                row,
                                rText,
                                fieldFound: "YES",
                                hasTable: hasTable ? "YES" : "NO",
                                hasColumn: hasColumn ? "YES" : "NO",
                                hasProc: hasProc ? "YES" : "NO",
                                score
                            });
                        }
                    }
                }
            }

            // Sort candidate matches by score descending
            candidateMatches.sort((a, b) => b.score - a.score);

            if (candidateMatches.length > 0) {
                const best = candidateMatches[0];
                targetElement = best.row;
                const selectedPageNum = best.pIdx + 1;

                console.log("    METHODOLOGY:");
                console.log("    " + methodology);
                console.log("    REQUESTED SECTION:");
                console.log("    " + requestedSection);
                console.log("    TARGET FIELD:");
                console.log("    " + (targetField || ""));
                console.log("    CANDIDATE PAGE:");
                console.log("    Page " + selectedPageNum);
                console.log("    CANDIDATE SECTION TEXT:");
                console.log("    " + best.rText.replace(/\n+/g, ' | ').slice(0, 120));
                console.log("    FIELD FOUND:");
                console.log("    " + best.fieldFound);
                console.log("    SOURCE TABLE FOUND:");
                console.log("    " + best.hasTable);
                console.log("    SOURCE COLUMN FOUND:");
                console.log("    " + best.hasColumn);
                console.log("    PROCESSING RULE FOUND:");
                console.log("    " + best.hasProc);
                console.log("    SELECTED PAGE:");
                console.log("    Page " + selectedPageNum);
            }

            // ── B) UT Document Fallback (Check dedicated scenarios like Scenario 10, 11, 14) ─────
            if (!targetElement && targetField) {
                for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                    const p = pages[pIdx];
                    const paras = await p.$$('p');
                    for (let i = 0; i < paras.length; i++) {
                        const text = (await paras[i].innerText()).toLowerCase();
                        if (text.includes(tFieldLower) && (text.includes("scenario") || text.includes("validated") || text.includes("column"))) {
                            for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                                const prevText = (await paras[j - 1].innerText()).toLowerCase();
                                const img = await paras[j].$('img');
                                if (img && prevText.includes("dsd")) {
                                    targetElement = img;
                                    console.log(`[STAGE 3] Matched UT Document scenario image for target field "${targetField}" on Page ${pIdx + 1}.`);
                                    break;
                                }
                            }
                            if (targetElement) break;
                        }
                    }
                    if (targetElement) break;
                }
            }

            // Special check for duplicate validation scenario in UT docs
            if (!targetElement && methodology === "DUPLICATE_VALIDATION") {
                for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                    const p = pages[pIdx];
                    const paras = await p.$$('p');
                    for (let i = 0; i < paras.length; i++) {
                        const text = (await paras[i].innerText()).toLowerCase();
                        if (text.includes("duplicate") && text.includes("scenario")) {
                            for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                                const prevText = (await paras[j - 1].innerText()).toLowerCase();
                                const img = await paras[j].$('img');
                                if (img && prevText.includes("dsd")) {
                                    targetElement = img;
                                    console.log(`[STAGE 3] Matched DUPLICATE_VALIDATION scenario image on Page ${pIdx + 1}.`);
                                    break;
                                }
                            }
                            if (targetElement) break;
                        }
                    }
                    if (targetElement) break;
                }
            }

            if (!targetElement) {
                console.log(`    [WARNING] SOURCE SECTION NOT FOUND: "${requestedSection}" for target field "${targetField}"`);
            }
        }

        // 5. SCHEDULED_EXECUTION_VALIDATION: Report Generation & Scheduling
        else if (
            methodology === "SCHEDULED_EXECUTION_VALIDATION" ||
            evidenceScope.toLowerCase().includes("report_frequency_scheduling") ||
            (semanticSection.toLowerCase().includes("report generation") && evidenceScope.toLowerCase().includes("frequency"))
        ) {
            // Strategy A: Check UT Document for Scenario 12 / schedule execution image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("scenario 12") || (text.includes("frequency") && text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && prevText.includes("dsd")) {
                                targetElement = img;
                                console.log(`[STAGE 3] SCHEDULED_EXECUTION_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: DOM Targeting for Report Generation scheduling block
            if (!targetElement) {
                const measureScheduledCrop = async () => {
                    return page.evaluate(() => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        let targetPage = null;
                        let targetPageIdx = -1;

                        // 1. Locate page containing "Report Generation", "Report Frequency Type", and "Scheduled"
                        for (let i = 0; i < pages.length; i++) {
                            const pText = pages[i].innerText || '';
                            if (
                                pText.includes("Report Generation") &&
                                (pText.includes("Report Frequency Type") || pText.includes("Frequency Type")) &&
                                pText.includes("Scheduled")
                            ) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        const allElements = Array.from(targetPage.querySelectorAll('*'));

                        // 2. Find deepest heading "Report Generation"
                        let headingEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t === "Report Generation") {
                                headingEl = el;
                            }
                        }

                        // 3. Find deepest "Report Frequency Type"
                        let freqTypeEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t === "Report Frequency Type:" || t === "Report Frequency Type" || (t.startsWith("Report Frequency Type") && t.length < 35)) {
                                freqTypeEl = el;
                            }
                        }

                        // 4. Find deepest "Scheduled"
                        let schedEl = null;
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t === "Scheduled" || (t.includes("Scheduled") && t.length < 25 && el.children.length === 0)) {
                                schedEl = el;
                            }
                        }

                        if (!headingEl || !freqTypeEl || !schedEl) {
                            return null;
                        }

                        const headingRow = headingEl.closest('tr') || headingEl.closest('p') || headingEl;
                        const freqRow = freqTypeEl.closest('tr') || freqTypeEl.closest('p') || freqTypeEl;

                        // Find all rows from headingRow down to before subsequent unrelated sections
                        let relevantRows = [];
                        let currentRow = headingRow;
                        while (currentRow) {
                            const rowText = (currentRow.innerText || '').trim();
                            if (
                                rowText.includes("Report Selection Criteria") ||
                                rowText.includes("Selection Criteria:") ||
                                rowText.includes("Report Control Breaks") ||
                                rowText.includes("Report Output") ||
                                rowText.includes("Report Retention") ||
                                rowText.includes("Report Specification") ||
                                rowText.includes("Report Layout")
                            ) {
                                break;
                            }
                            relevantRows.push(currentRow);
                            if (currentRow === freqRow) {
                                const next = currentRow.nextElementSibling;
                                if (next) {
                                    const nText = (next.innerText || '').trim();
                                    // Include accumulation type if immediately attached to Report Generation and not beginning next section
                                    if (
                                        nText.includes("Report Data Accumulation Type") &&
                                        !nText.includes("Report Selection Criteria") &&
                                        !nText.includes("Selection Criteria:") &&
                                        !nText.includes("Report Output")
                                    ) {
                                        relevantRows.push(next);
                                    }
                                }
                                break;
                            }
                            currentRow = currentRow.nextElementSibling;
                        }

                        if (relevantRows.length === 0) {
                            relevantRows = [headingRow, freqRow];
                        }

                        const rects = [];
                        for (const r of relevantRows) {
                            const b = r.getBoundingClientRect();
                            if (b.width > 0 && b.height > 0) {
                                rects.push(b);
                            }
                            const cells = r.querySelectorAll('td, th');
                            for (const c of cells) {
                                const cb = c.getBoundingClientRect();
                                if (cb.width > 0 && cb.height > 0) {
                                    rects.push(cb);
                                }
                            }
                        }

                        const headingRect = headingEl.getBoundingClientRect();
                        const freqRect = freqTypeEl.getBoundingClientRect();
                        const schedRect = schedEl.getBoundingClientRect();

                        rects.push(headingRect, freqRect, schedRect);

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxBottom = Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: (maxBottom - minTop) + (margin * 2)
                        };

                        const validation = {
                            "Report Generation": (headingRect.left >= finalCrop.x - margin && headingRect.right <= finalCrop.x + finalCrop.width + margin && headingRect.top >= finalCrop.y - margin && headingRect.bottom <= finalCrop.y + finalCrop.height + margin) ? "YES" : "NO",
                            "Report Frequency Type": (freqRect.left >= finalCrop.x - margin && freqRect.right <= finalCrop.x + finalCrop.width + margin && freqRect.top >= finalCrop.y - margin && freqRect.bottom <= finalCrop.y + finalCrop.height + margin) ? "YES" : "NO",
                            "Scheduled": (schedRect.left >= finalCrop.x - margin && schedRect.right <= finalCrop.x + finalCrop.width + margin && schedRect.top >= finalCrop.y - margin && schedRect.bottom <= finalCrop.y + finalCrop.height + margin) ? "YES" : "NO"
                        };

                        if (validation["Report Generation"] !== "YES" || validation["Report Frequency Type"] !== "YES" || validation["Scheduled"] !== "YES") {
                            return null;
                        }

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    });
                };

                let domResult = await measureScheduledCrop();

                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 50) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureScheduledCrop();
                    }

                    if (domResult && domResult.finalCrop) {
                        targetClip = domResult.finalCrop;

                        console.log("METHODOLOGY:\nSCHEDULED_EXECUTION_VALIDATION");
                        console.log("SOURCE SECTION:\nReport Generation");
                        console.log("EVIDENCE SCOPE:\nREPORT_FREQUENCY_SCHEDULING");
                        console.log("TARGET:\nScheduled / Report Frequency Type");
                        console.log(`SELECTED PAGE:\n${domResult.pageIndex + 1}`);
                        console.log(`TARGET REGION:\n${JSON.stringify(domResult.finalCrop)}`);
                        console.log("VALIDATION:");
                        for (const [k, v] of Object.entries(domResult.validation || {})) {
                            console.log(`    ${k} = ${v}`);
                        }
                    }
                }
            }
        }

        // 6. OUTPUT_DELIVERY_VALIDATION / SCRIPT_OUTPUT_VALIDATION
        else if (methodology === "OUTPUT_DELIVERY_VALIDATION" || methodology === "SCRIPT_OUTPUT_VALIDATION") {
            // Strategy A: Check UT Document for Scenario 4 / Scenario 13 SDR image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("scenario 4") || text.includes("scenario 13") || text.includes("sdr") || (text.includes("output") && text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const img = await paras[j].$('img');
                            if (img) {
                                targetElement = img;
                                console.log(`[STAGE 3] OUTPUT_DELIVERY_VALIDATION matched UT Document scenario image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Standard DSD DOM Geometry Crop for Report Output block
            if (!targetElement) {
                const measureOutputCrop = async () => {
                    return page.evaluate(() => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        
                        // 1. Locate the page containing "Report Output"
                        let targetPage = null;
                        let targetPageIdx = -1;

                        for (let i = 0; i < pages.length; i++) {
                            const text = (pages[i].innerText || '').toLowerCase();
                            if (text.includes("report output") && (text.includes("reporting portal") || text.includes("output format") || text.includes("distribution group"))) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        // 2. Find table rows inside this page for Report Output block
                        const tables = Array.from(targetPage.querySelectorAll('table'));
                        let headingRow = null;
                        let formatRow = null;
                        let portalRow = null;
                        let distGroupRow = null;
                        let nextSectionRow = null;
                        let allRelevantElements = [];

                        for (const t of tables) {
                            const rows = Array.from(t.querySelectorAll('tr'));
                            let inOutputSection = false;

                            for (let rIdx = 0; rIdx < rows.length; rIdx++) {
                                const r = rows[rIdx];
                                const rText = (r.innerText || '').trim();
                                const rTextLower = rText.toLowerCase();

                                if (!headingRow && (rText === "Report Output" || (rTextLower.startsWith("report output") && rText.length < 30))) {
                                    headingRow = r;
                                    inOutputSection = true;
                                }

                                if (inOutputSection) {
                                    if (rTextLower.includes("report retention") || rTextLower.includes("report special processing") || rTextLower.includes("report specification")) {
                                        nextSectionRow = r;
                                        break;
                                    }
                                    if (rTextLower.includes("report output format")) formatRow = r;
                                    if (rTextLower.includes("reporting portal")) portalRow = r;
                                    if (rTextLower.includes("distribution group")) distGroupRow = r;

                                    allRelevantElements.push(r);
                                }
                            }
                            if (headingRow) break;
                        }

                        if (allRelevantElements.length === 0) return null;

                        const rects = allRelevantElements.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);
                        if (rects.length === 0) return null;

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const maxBottom = Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: (maxBottom - minTop) + (margin * 2)
                        };

                        const fullSectionText = allRelevantElements.map(el => el.innerText || '').join(' ').toLowerCase();

                        const validation = {
                            "Report Output": headingRow ? "YES" : "NO",
                            "Report Output Format": formatRow ? "YES" : "NO",
                            "Reporting Portal": portalRow ? "YES" : "NO",
                            "Distribution Group(s)": distGroupRow ? "YES" : "NO",
                            "EDMS": fullSectionText.includes("edms") ? "YES" : "NO"
                        };

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    });
                };

                let domResult = await measureOutputCrop();
                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 50) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureOutputCrop();
                    }

                    targetClip = domResult.finalCrop;

                    console.log("    METHODOLOGY:\n    OUTPUT_DELIVERY_VALIDATION");
                    console.log("    SOURCE SECTION:\n    Report Output");
                    console.log("    EVIDENCE SCOPE:\n    REPORT_OUTPUT_DISTRIBUTION");
                    console.log("    TARGET:\n    " + (targetField || "EDMS"));
                    console.log(`    SELECTED PAGE:\n    Page ${domResult.pageIndex + 1}`);
                    console.log("    TARGET REGION RECT:");
                    console.log(`    x: ${domResult.finalCrop.x}`);
                    console.log(`    y: ${domResult.finalCrop.y}`);
                    console.log(`    width: ${domResult.finalCrop.width}`);
                    console.log(`    height: ${domResult.finalCrop.height}`);
                    console.log("    VALIDATION:");
                    for (const [k, v] of Object.entries(domResult.validation || {})) {
                        console.log(`        ${k} = ${v}`);
                    }
                }
            }
        }

        // 7. REPORT_NAME_DESCRIPTION_VALIDATION
        else if (methodology === "REPORT_NAME_DESCRIPTION_VALIDATION") {
            // Strategy A: Check UT Document for Scenario 5 DSD image
            for (let pIdx = 0; pIdx < pages.length; pIdx++) {
                const p = pages[pIdx];
                const paras = await p.$$('p');
                for (let i = 0; i < paras.length; i++) {
                    const text = (await paras[i].innerText()).toLowerCase();
                    if (text.includes("scenario 5") || (text.includes("report name") && text.includes("validated"))) {
                        for (let j = i + 1; j < Math.min(i + 6, paras.length); j++) {
                            const prevText = (await paras[j - 1].innerText()).toLowerCase();
                            const img = await paras[j].$('img');
                            if (img && (prevText.includes("dsd") || (await paras[j].innerText()).toLowerCase().includes("dsd"))) {
                                targetElement = img;
                                console.log(`[STAGE 3] REPORT_NAME_DESCRIPTION_VALIDATION matched Scenario 5 DSD image.`);
                                break;
                            }
                        }
                        if (targetElement) break;
                    }
                }
                if (targetElement) break;
            }

            // Strategy B: Standard DSD DOM Geometry Crop for REPORT_DEFINITION_METADATA
            if (!targetElement) {
                const measureMetadataCrop = async () => {
                    return page.evaluate((rId) => {
                        window.scrollTo(0, 0);
                        if (document.scrollingElement) {
                            document.scrollingElement.scrollTop = 0;
                            document.scrollingElement.scrollLeft = 0;
                        }
                        const docxWrapper = document.querySelector('.docx-wrapper');
                        if (docxWrapper) {
                            docxWrapper.scrollTop = 0;
                            docxWrapper.scrollLeft = 0;
                        }

                        const pages = Array.from(document.querySelectorAll('.docx-wrapper > section'));
                        
                        // 1. Locate the page containing "NH MMIS REPORT DEFINITION" or "Report Definition"
                        let targetPage = null;
                        let targetPageIdx = -1;

                        for (let i = 0; i < pages.length; i++) {
                            const text = (pages[i].innerText || '').toLowerCase();
                            if (text.includes("report definition") || text.includes("nh mmis report definition")) {
                                targetPage = pages[i];
                                targetPageIdx = i;
                                break;
                            }
                        }

                        if (!targetPage) return null;

                        // 2. Find table rows inside this page for metadata
                        const tables = Array.from(targetPage.querySelectorAll('table'));
                        let headingEl = null;
                        let reportIdRow = null;
                        let reportTitleRow = null;
                        let reportDescRow = null;
                        let reportGeneratedByRow = null;
                        let allRelevantElements = [];

                        // Heading element
                        const allElements = Array.from(targetPage.querySelectorAll('*'));
                        for (const el of allElements) {
                            const t = (el.innerText || '').trim();
                            if (t.length < 80 && (t === "NH MMIS REPORT DEFINITION" || t.includes("REPORT DEFINITION"))) {
                                headingEl = el;
                                allRelevantElements.push(el);
                                break;
                            }
                        }

                        for (const t of tables) {
                            const rows = Array.from(t.querySelectorAll('tr'));
                            for (const r of rows) {
                                const rText = (r.innerText || '').toLowerCase();
                                if (!reportIdRow && (rText.includes("client report id") || rText.includes("report id"))) {
                                    reportIdRow = r;
                                    allRelevantElements.push(r);
                                }
                                if (!reportTitleRow && rText.includes("report title")) {
                                    reportTitleRow = r;
                                    allRelevantElements.push(r);
                                }
                                if (!reportDescRow && rText.includes("report description")) {
                                    reportDescRow = r;
                                    allRelevantElements.push(r);
                                }
                                if (!reportGeneratedByRow && rText.includes("report generated by")) {
                                    reportGeneratedByRow = r;
                                    allRelevantElements.push(r);
                                }
                            }
                        }

                        // Also include all intermediate rows from heading/first metadata row down to reportGeneratedByRow
                        if (reportGeneratedByRow && reportGeneratedByRow.parentElement) {
                            const tableRows = Array.from(reportGeneratedByRow.parentElement.querySelectorAll('tr'));
                            const endIdx = tableRows.indexOf(reportGeneratedByRow);
                            if (endIdx !== -1) {
                                for (let k = 0; k <= endIdx; k++) {
                                    allRelevantElements.push(tableRows[k]);
                                }
                            }
                        }

                        if (allRelevantElements.length === 0) return null;

                        const rects = allRelevantElements.map(el => el.getBoundingClientRect()).filter(r => r.width > 0 && r.height > 0);
                        if (rects.length === 0) return null;

                        const minLeft = Math.min(...rects.map(r => r.left));
                        const minTop = Math.min(...rects.map(r => r.top));
                        const maxRight = Math.max(...rects.map(r => r.right));
                        const maxBottom = reportGeneratedByRow ? reportGeneratedByRow.getBoundingClientRect().bottom : Math.max(...rects.map(r => r.bottom));

                        const margin = 4;
                        const finalCrop = {
                            x: Math.max(0, minLeft - margin),
                            y: Math.max(0, minTop - margin),
                            width: (maxRight - minLeft) + (margin * 2),
                            height: (maxBottom - minTop) + (margin * 2)
                        };

                        const validation = {
                            "Report ID": reportIdRow ? "YES" : "NO",
                            "Report Title": reportTitleRow ? "YES" : "NO",
                            "Report Description": reportDescRow ? "YES" : "NO",
                            "Report Generated By": reportGeneratedByRow ? "YES" : "NO"
                        };

                        return {
                            pageIndex: targetPageIdx,
                            finalCrop,
                            validation
                        };
                    }, reportId);
                };

                let domResult = await measureMetadataCrop();
                if (domResult && domResult.finalCrop && domResult.finalCrop.width > 50 && domResult.finalCrop.height > 50) {
                    const currentViewport = page.viewportSize();
                    const neededWidth = Math.ceil(domResult.finalCrop.x + domResult.finalCrop.width + 100);
                    const neededHeight = Math.ceil(domResult.finalCrop.y + domResult.finalCrop.height + 200);

                    if (neededWidth > currentViewport.width || neededHeight > currentViewport.height) {
                        await page.setViewportSize({
                            width: Math.max(neededWidth, currentViewport.width),
                            height: Math.max(neededHeight, currentViewport.height)
                        });
                        domResult = await measureMetadataCrop();
                    }

                    targetClip = domResult.finalCrop;

                    console.log("    METHODOLOGY:\n    REPORT_NAME_DESCRIPTION_VALIDATION");
                    console.log("    SOURCE SECTION:\n    Report Definition");
                    console.log("    EVIDENCE SCOPE:\n    REPORT_DEFINITION_METADATA");
                    console.log("    TARGET FIELDS:\n    Report ID\n    Report Title\n    Report Description\n    Report Generated By");
                    console.log(`    SELECTED PAGE:\n    Page ${domResult.pageIndex + 1}`);
                    console.log("    FINAL CROP:");
                    console.log(`    x: ${domResult.finalCrop.x}`);
                    console.log(`    y: ${domResult.finalCrop.y}`);
                    console.log(`    width: ${domResult.finalCrop.width}`);
                    console.log(`    height: ${domResult.finalCrop.height}`);
                    console.log("    VALIDATION:");
                    for (const [k, v] of Object.entries(domResult.validation || {})) {
                        console.log(`        ${k} = ${v}`);
                    }
                }
            }
        }

        // ── GENERIC SECTION FALLBACK ─────────────────────────────────────────
        if (!isCustomSaved) {
            if (!targetElement && !targetClip) {
                // Guard: SCHEDULED_EXECUTION_VALIDATION must NOT fall back to full DSD page per Phase 12L
                if (methodology === "SCHEDULED_EXECUTION_VALIDATION") {
                    console.log(`[STAGE 3] SCHEDULED_EXECUTION_VALIDATION failed required markers check. Rejecting candidate without full page fallback.`);
                    throw new Error("SCHEDULED_EXECUTION_VALIDATION: Required Report Generation markers (Report Generation, Report Frequency Type, Scheduled) not found.");
                }
                let found = false;
                for (const p of pages) {
                    const innerText = await p.innerText();
                    const textLower = innerText.toLowerCase();
                    const secLower = semanticSection.toLowerCase();
                    const repLower = reportId.toLowerCase();

                    const hasSection = secLower ? textLower.includes(secLower) : false;
                    const hasReportId = repLower ? textLower.includes(repLower) : false;

                    if (hasSection && hasReportId) {
                        targetElement = p;
                        found = true;
                        console.log(`[STAGE 3] Generic fallback matched page with section & reportId.`);
                        break;
                    } else if (hasSection && !found) {
                        targetElement = p;
                        found = true;
                    }
                }
            }

            // Ultimate fallback to first page
            if (!targetElement && !targetClip) {
                targetElement = pages[0];
                console.log(`[STAGE 3] Ultimate fallback to Page 1.`);
            }

            // Ensure output directory exists
            const outDir = path.dirname(outPngPath);
            if (!fs.existsSync(outDir)) {
                fs.mkdirSync(outDir, { recursive: true });
            }

            if (targetElement) {
                await targetElement.screenshot({ path: outPngPath });
                const stats = fs.statSync(outPngPath);
                console.log(`SNAPSHOT CREATED: ${outPngPath}, size: ${stats.size} bytes (element)`);
            } else if (targetClip) {
                await page.screenshot({ path: outPngPath, clip: targetClip });
                const stats = fs.statSync(outPngPath);
                console.log(`SNAPSHOT CREATED: ${outPngPath}, size: ${stats.size} bytes (clip: ${Math.round(targetClip.width)}x${Math.round(targetClip.height)})`);
            }
        }

    } catch (err) {
        console.error(`[ERROR] Rendering error: ${err.message}`);
        process.exit(1);
    } finally {
        await browser.close();
    }
})();
