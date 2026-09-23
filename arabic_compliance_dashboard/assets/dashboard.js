const __arCfg = window.__AR_DASHBOARD__ || {};
        const __arApiBase = String(__arCfg.apiBase || "").replace(/\/+$/, "");
        function arApiUrl(path) {
            const p = path.startsWith("/") ? path : "/" + path;
            if (__arApiBase) return __arApiBase + p;
            return "/api" + (p.startsWith("/api") ? p.slice(4) : p);
        }

        const hasChartLib = typeof Chart !== "undefined";
        const hasChartDataLabels = typeof ChartDataLabels !== "undefined";
        if (hasChartLib && hasChartDataLabels) {
            Chart.register(ChartDataLabels);
        }

        (function installSnapshotFetchShim() {
            const packEl = document.getElementById("snapshot-pack");
            if (!packEl) return;
            let pack;
            try {
                pack = JSON.parse(packEl.textContent || "{}");
            } catch {
                return;
            }
            const BLANK = "(blank)";
            const COL_YEAR = "تاريخ خطة الالتزام";
            const COL_ASSESSMENT = "نتائج التقييم خلال السنة الحالية";
            const DATE_YEAR_COLS = [
                COL_YEAR,
                "تاريخ التصحيح السنوي المستهدف",
                "تاريخ التصحيح السنوي الفعلي"
            ];
            const DATE_QUARTER_COLS = [
                "تاريخ التصحيح المستهدف - الربعي",
                "تاريخ التصحيح الفعلي - الربعي"
            ];
            const COL_TARGET = "تاريخ التصحيح المستهدف";
            const COL_MODIFIED = "تاريخ التصحيح المعدل";
            const COL_STATUS = "حالة الخطة التصحيحية";
            const COL_RESIDUAL = "تصنيف المخاطر المتبقية";
            const COL_INHERENT = "مستوى المخاطر الكامنة";
            const COL_FINAL_PREV = "حالة الالتزام النهائي بالمتطلبات للسنة السابقة";
            const COL_FINAL_CURR = "حالة الالتزام النهائي بالمتطلبات للسنة الحالية";
            const COL_DETAILED_REPORT = "التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي";
            const PARAM_TO_COL = {
                inherent: "مستوى المخاطر الكامنة",
                residual: "تصنيف المخاطر المتبقية",
                status: "حالة الخطة التصحيحية",
                year: "تاريخ خطة الالتزام",
                assessment_year: "نتائج التقييم خلال السنة الحالية",
                target_annual: "تاريخ التصحيح السنوي المستهدف",
                target_quarterly: "تاريخ التصحيح المستهدف - الربعي",
                actual_annual: "تاريخ التصحيح السنوي الفعلي",
                actual_quarterly: "تاريخ التصحيح الفعلي - الربعي",
                department: "الإدارة المسؤولة",
                legislator: "المشرع",
                system_name: "اسم النظام",
                authority: "الهيئة التابعة",
                regulation: "اللائحة",
                legal_text: "النص النظامي",
                compliance_status: "حالة الالتزام بالمتطلبات",
                control_category: "فئة الضوابط الرقابية",
                subsidiary_company: "الشركة التابعة",
                holding_company: "الشركة القابضة"
            };
            const GROUP_DIMS = Object.values(PARAM_TO_COL);
            const selectedFromParams = (sp) => {
                const out = {};
                Object.entries(PARAM_TO_COL).forEach(([p, col]) => {
                    out[col] = sp.getAll(p).map((v) => String(v).trim()).filter(Boolean);
                });
                return out;
            };
            const rowValue = (row, col) => {
                const v = row[col];
                return v === undefined || v === null || v === "" ? BLANK : String(v);
            };
            const yearFromDateCell = (value) => {
                if (value === undefined || value === null || value === "" || value === BLANK) return BLANK;
                const s = String(value).trim();
                const yOnly = s.match(/^(\d{4})(?:\.0+)?$/);
                if (yOnly) {
                    const y = Number(yOnly[1]);
                    if (y >= 1900 && y <= 2100) return String(y);
                }
                if (/^-?\d+(?:\.\d+)?$/.test(s)) {
                    const n = Number(s);
                    if (Number.isFinite(n)) {
                        let ms = null;
                        if (n >= 1e12) ms = n;
                        else if (n >= 1e9) ms = n * 1000;
                        if (ms != null) {
                            const dEpoch = new Date(ms);
                            if (!Number.isNaN(dEpoch.getTime())) return String(dEpoch.getUTCFullYear());
                        }
                    }
                }
                const d = new Date(`${s.slice(0, 10)}T12:00:00`);
                return Number.isNaN(d.getTime()) ? BLANK : String(d.getFullYear());
            };
            const enrichRowYear = (row) => {
                const existing = rowValue(row, COL_YEAR);
                if (existing !== BLANK) {
                    if (/^\d{4}$/.test(String(existing).trim())) return row;
                    const extracted = yearFromDateCell(existing);
                    if (extracted !== BLANK) row[COL_YEAR] = extracted;
                    return row;
                }
                const annual = rowValue(row, "تاريخ التصحيح السنوي المستهدف");
                row[COL_YEAR] = yearFromDateCell(annual !== BLANK ? annual : rowValue(row, COL_TARGET));
                return row;
            };
            const enrichRowDateDims = (row) => {
                DATE_YEAR_COLS.forEach((col) => {
                    if (col === COL_YEAR) return;
                    let existing = rowValue(row, col);
                    let parsed = yearFromDateCell(existing);
                    if (parsed === BLANK) {
                        const fallbackCol = col === "تاريخ التصحيح السنوي المستهدف"
                            ? COL_TARGET
                            : col === "تاريخ التصحيح السنوي الفعلي"
                                ? "تاريخ التصحيح الفعلي"
                                : "";
                        if (fallbackCol) {
                            parsed = yearFromDateCell(rowValue(row, fallbackCol));
                        }
                    }
                    if (parsed !== BLANK) {
                        row[col] = parsed;
                    }
                });
                DATE_QUARTER_COLS.forEach((col) => {
                    const existing = rowValue(row, col);
                    if (existing === BLANK) {
                        row[col] = BLANK;
                        return;
                    }
                    if (/^\d{4}-Q[1-4]$/i.test(String(existing).trim())) return;
                    const rawQ = String(existing).trim();
                    const yq = rawQ.match(/^(\d{4})\s*-?\s*Q\s*([1-4])$/i);
                    const qy = rawQ.match(/^Q\s*([1-4])\s*-?\s*(\d{4})$/i);
                    if (yq) {
                        row[col] = `${yq[1]}-Q${yq[2]}`;
                        return;
                    }
                    if (qy) {
                        row[col] = `${qy[2]}-Q${qy[1]}`;
                        return;
                    }
                    if (/^Q\s*[1-4]$/i.test(rawQ) || /^الربع\s*[1-4]$/.test(rawQ)) {
                        const n = (rawQ.match(/[1-4]/) || [])[0];
                        const yearSrc = col.includes("الفعلي")
                            ? rowValue(row, "تاريخ التصحيح السنوي الفعلي")
                            : rowValue(row, "تاريخ التصحيح السنوي المستهدف");
                        let y = yearFromDateCell(yearSrc);
                        if (y === BLANK) y = yearFromDateCell(rowValue(row, COL_YEAR));
                        if (y === BLANK) y = yearFromDateCell(rowValue(row, COL_TARGET));
                        row[col] = y !== BLANK ? `${y}-Q${n}` : `Q${n}`;
                        return;
                    }
                    const d = yearFromDateCell(existing);
                    const parsed = new Date(`${String(existing).slice(0, 10)}T12:00:00`);
                    if (!Number.isNaN(parsed.getTime())) {
                        const q = Math.floor(parsed.getMonth() / 3) + 1;
                        row[col] = `${parsed.getFullYear()}-Q${q}`;
                    } else if (d !== BLANK) {
                        row[col] = d;
                    }
                });
                let assess = rowValue(row, COL_ASSESSMENT);
                if (assess === BLANK) {
                    assess = rowValue(row, "تاريخ نتائج التقييم خلال السنة الحالية");
                }
                if (assess !== BLANK) {
                    const rawQ = String(assess).trim();
                    const qOnly = rawQ.match(/Q\s*([1-4])/i) || rawQ.match(/الربع\s*([1-4])/);
                    const yq = rawQ.match(/(?:\d{4}\s*-?\s*)Q\s*([1-4])/i);
                    if (qOnly) {
                        row[COL_ASSESSMENT] = `Q${qOnly[1]}`;
                    } else if (yq) {
                        row[COL_ASSESSMENT] = `Q${yq[1]}`;
                    } else {
                        row[COL_ASSESSMENT] = rawQ;
                    }
                }
                return row;
            };
            const applyFilters = (rows, selected, skipCol) =>
                rows.filter((row) =>
                    Object.entries(selected).every(([col, vals]) => col === skipCol || !vals?.length || vals.includes(rowValue(row, col)))
                );
            const sortGroup = (key, values) => {
                if (key === COL_ASSESSMENT) {
                    const quarters = values
                        .filter((v) => /^Q[1-4]$/i.test(v))
                        .sort((a, b) => Number(a.slice(-1)) - Number(b.slice(-1)));
                    const rest = values
                        .filter((v) => !/^Q[1-4]$/i.test(v) && v !== BLANK)
                        .sort((a, b) => a.localeCompare(b, "ar"));
                    const ordered = [...quarters, ...rest];
                    return values.includes(BLANK) ? [BLANK, ...ordered] : ordered;
                }
                if (DATE_YEAR_COLS.includes(key) || DATE_QUARTER_COLS.includes(key)) {
                    const numeric = values.filter((v) => /^\d+$/.test(v)).sort((a, b) => Number(a) - Number(b));
                    const quarters = values
                        .filter((v) => /^\d{4}-Q[1-4]$/i.test(v))
                        .sort((a, b) => Number(a.slice(0, 4)) - Number(b.slice(0, 4)) || Number(a.slice(-1)) - Number(b.slice(-1)));
                    const rest = values
                        .filter((v) => !/^\d+$/.test(v) && !/^\d{4}-Q[1-4]$/i.test(v) && v !== BLANK)
                        .sort((a, b) => a.localeCompare(b, "ar"));
                    const ordered = [...numeric, ...quarters, ...rest];
                    return values.includes(BLANK) ? [BLANK, ...ordered] : ordered;
                }
                return [...values].sort((a, b) => a.localeCompare(b, "ar"));
            };
            const buildSummary = (rows, selected) => {
                const fully = applyFilters(rows, selected, null);
                const groups = {};
                const availableDims = GROUP_DIMS.filter((dim) =>
                    rows.some((r) => Object.prototype.hasOwnProperty.call(r, dim))
                );
                availableDims.forEach((dim) => {
                    const counts = {};
                    applyFilters(rows, selected, dim).forEach((r) => {
                        const k = rowValue(r, dim);
                        counts[k] = (counts[k] || 0) + 1;
                    });
                    groups[dim] = sortGroup(dim, Object.keys(counts)).map((k) => ({ key: k, label: k, count: counts[k] }));
                });
                const company_columns = {
                    holding: availableDims.includes("الشركة القابضة"),
                    subsidiary: availableDims.includes("الشركة التابعة")
                };
                return { total: fully.length, selected, groups, company_columns };
            };
            const detailFields = [
                ["المشرع", "المشرع"],
                ["حالة الخطة التصحيحية", "حالة الخطة التصحيحية"],
                ["مستوى المخاطر الكامنة", "مستوى المخاطر الكامنة"],
                ["تصنيف المخاطر المتبقية", "تصنيف المخاطر المتبقية"],
                ["فئة الضوابط الرقابية", "فئة الضوابط الرقابية"],
                ["نتائج التقييم خلال السنة الحالية", "نتائج التقييم خلال السنة الحالية"],
                ["تاريخ التصحيح المستهدف", "تاريخ التصحيح المستهدف"],
                ["مالك المهمة / مالك الإجراء", "مالك المهمة / مالك الإجراء"],
                ["الشخص المسؤول", "الشخص المسؤول"],
                ["الخطة التصحيحية", "الخطة التصحيحية"],
                ["البنود/المتطلبات غير الملتزم بها", "البنود/المتطلبات غير الملتزم بها"]
            ];
            const detailColAliases = {
                "نتائج التقييم خلال السنة الحالية": [
                    "نتائج التقييم خلال السنة الحالية",
                    "تاريخ نتائج التقييم خلال السنة الحالية"
                ],
                "حالة الخطة التصحيحية": ["حالة الخطة التصحيحية", "الحالة"],
                "البنود/المتطلبات غير الملتزم بها": [
                    "البنود/المتطلبات غير الملتزم بها",
                    "ملاحظات الإلتزام",
                    "ملاحظات الالتزام"
                ],
                "ملاحظات الإدارة.1": ["ملاحظات الإدارة.1", "ملاحظات الإدارة"]
            };
            const formatDisplayDate = (value) => {
                const s = String(value || "").trim();
                if (!s || s === BLANK) return "";
                if (/^-?\d+(?:\.\d+)?$/.test(s)) {
                    const n = Number(s);
                    if (Number.isFinite(n)) {
                        if (n >= 1e12) {
                            const d = new Date(n);
                            if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
                        }
                        if (n >= 1e9) {
                            const d = new Date(n * 1000);
                            if (!Number.isNaN(d.getTime())) return d.toISOString().slice(0, 10);
                        }
                    }
                }
                const d = new Date(`${s.slice(0, 10)}T12:00:00`);
                return Number.isNaN(d.getTime()) ? s : s.slice(0, 10);
            };
            const detailValue = (row, col) => {
                const aliases = detailColAliases[col] || [col];
                let raw = BLANK;
                for (const alias of aliases) {
                    raw = rowValue(row, alias);
                    if (raw !== BLANK) break;
                }
                if (raw === BLANK) return "";
                if (col === COL_TARGET || col === COL_MODIFIED) {
                    return formatDisplayDate(raw) || raw;
                }
                return raw;
            };
            const pickBestLegalRow = (matches) => {
                if (!matches.length) return null;
                const withMail = matches.filter((r) => {
                    const e = rowValue(r, "email");
                    return e !== BLANK && String(e).includes("@");
                });
                const pool = withMail.length ? withMail : matches;
                let best = pool[0];
                let bestScore = -1;
                pool.forEach((r) => {
                    let s = 0;
                    detailFields.forEach(([col]) => {
                        if (detailValue(r, col)) s += 1;
                    });
                    if (s > bestScore) {
                        bestScore = s;
                        best = r;
                    }
                });
                return best;
            };
            const legalDetailsFromRows = (text) => {
                const matches = rows.filter((r) => rowValue(r, "النص النظامي") === text);
                if (!matches.length) return null;
                const row = pickBestLegalRow(matches);
                const fields = detailFields.map(([col, label]) => ({
                    label,
                    value: detailValue(row, col)
                }));
                const em = rowValue(row, "email");
                const recipient_email =
                    em !== BLANK && String(em).includes("@") ? String(em).trim() : "";
                return {
                    legal_text: text,
                    excel_row: 0,
                    picked_row_index: 0,
                    recipient_email,
                    fields,
                    images: []
                };
            };
            const normNFKC = (s) => String(s || "").normalize("NFKC");
            const isWithinCorrectionStatus = (statusText) => {
                const t = normNFKC(statusText).replace(/\s+/g, " ");
                if (!t.includes("مفتوح")) return false;
                return t.includes("ضمن") && t.includes("تاريخ") && t.includes("التصحيح");
            };
            const isPastCorrectionStatus = (statusText) => {
                const t = normNFKC(statusText).replace(/\s+/g, " ");
                if (!t.includes("مفتوح")) return false;
                return t.includes("تجاوز") && t.includes("تاريخ") && t.includes("التصحيح");
            };
            const isOpenStatusForAging = (statusText) =>
                isWithinCorrectionStatus(statusText) || isPastCorrectionStatus(statusText);
            const agingRowRiskText = (row) => {
                const residual = rowValue(row, COL_RESIDUAL);
                if (residual !== BLANK) return residual;
                return rowValue(row, COL_INHERENT);
            };
            const agingRiskKey = (residualNorm) => {
                if (residualNorm === BLANK) return null;
                let t = normNFKC(String(residualNorm || "").trim()).replace(/\u00a0/g, " ");
                if (!t) return null;
                t = t.replace(/\s+/g, " ").trim();
                [
                    ["مرنفع", "مرتفع"],
                    ["مرتفغ", "مرتفع"],
                    ["مرتفاع", "مرتفع"],
                    ["مرنفغ", "مرتفع"],
                    ["مرتفغ جدا", "مرتفع جدا"],
                    ["عاليه", "عالية"]
                ].forEach(([bad, good]) => (t = t.split(bad).join(good)));
                if (t.includes("متدني") && /انخفاض|انخفاظ|انخغاض|انخفاق/.test(t)) return "very_low";
                if ((t.includes("جدا") || t.includes("جداً") || t.includes("جدآ")) && (t.includes("مرتفع") || t.includes("مرفع") || t.includes("عالي") || t.includes("عالية"))) return "very_high";
                if (t.includes("متوسط")) return "medium";
                if (t.includes("منخفض") && !t.includes("متدني")) return "low";
                if (t.includes("مرتفع") || t.includes("مرفع")) return "high";
                if (/^(عالي|عالية)$/.test(t) || /(^|\s)عالي(?:ة)?($|\s)/.test(t)) return "high";
                return null;
            };
            const parseDateAtNoon = (dstr) => {
                if (!dstr || dstr === BLANK) return null;
                const s = String(dstr).trim();
                if (/^-?\d+(?:\.\d+)?$/.test(s)) {
                    const n = Number(s);
                    if (Number.isFinite(n)) {
                        let ms = null;
                        if (n >= 1e12) ms = n;
                        else if (n >= 1e9) ms = n * 1000;
                        if (ms != null) {
                            const dEpoch = new Date(ms);
                            if (!Number.isNaN(dEpoch.getTime())) {
                                return new Date(dEpoch.getFullYear(), dEpoch.getMonth(), dEpoch.getDate());
                            }
                        }
                        if (n >= 20000 && n <= 80000) {
                            const excel = new Date(Date.UTC(1899, 11, 30) + Math.round(n * 86400000));
                            if (!Number.isNaN(excel.getTime())) {
                                return new Date(excel.getUTCFullYear(), excel.getUTCMonth(), excel.getUTCDate());
                            }
                        }
                    }
                }
                const d = new Date(`${s.slice(0, 10)}T12:00:00`);
                return Number.isNaN(d.getTime()) ? null : d;
            };
            const isClosedStatusForAging = (statusText) => {
                const t = normNFKC(statusText).replace(/\s+/g, " ");
                return t.includes("مغلق") || t.includes("مقفل");
            };
            const agingTargetDate = (row) => {
                const wanted = COL_TARGET.replace(/\s+/g, " ").trim();
                const keys = [COL_TARGET, "تاريخ التصحيح  المستهدف", ...Object.keys(row || {})];
                const seen = new Set();
                for (const key of keys) {
                    if (seen.has(key)) continue;
                    seen.add(key);
                    if (String(key).replace(/\s+/g, " ").trim() !== wanted && key !== COL_TARGET && key !== "تاريخ التصحيح  المستهدف") {
                        continue;
                    }
                    const parsed = parseDateAtNoon(rowValue(row, key));
                    if (parsed) return parsed;
                }
                return null;
            };
            const agingOverdueDetail = (compare, reference) => {
                if (!compare || !reference) return [null, null];
                const cref = new Date(compare.getFullYear(), compare.getMonth(), compare.getDate());
                const rref = new Date(reference.getFullYear(), reference.getMonth(), reference.getDate());
                const overdueDays = Math.floor((rref - cref) / (1000 * 60 * 60 * 24));
                if (overdueDays < 183) return ["lt_6m", null];
                if (overdueDays < 365) return ["lt_1y", null];
                if (overdueDays < 730) return ["ge_1y", "y1_2"];
                if (overdueDays < 1095) return ["ge_1y", "y2_3"];
                if (overdueDays < 1460) return ["ge_1y", "y3_4"];
                if (overdueDays < 1825) return ["ge_1y", "y4_5"];
                return ["ge_1y", "y5p"];
            };
            const agingOverdueBucket = (compare, reference) => agingOverdueDetail(compare, reference)[0];
            const agingClassifyRow = (row, ref) => {
                const st = rowValue(row, COL_STATUS);
                const rkey = agingRiskKey(agingRowRiskText(row)) || "other";
                if (isClosedStatusForAging(st)) return null;
                const cdt = agingTargetDate(row);
                if (!cdt) return null;
                const cref = new Date(cdt.getFullYear(), cdt.getMonth(), cdt.getDate());
                const rref = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
                if (cref >= rref) return ["not_due", null, rkey];
                const [parent, child] = agingOverdueDetail(cdt, ref);
                if (!parent) return null;
                return [parent, child, rkey];
            };
            const agingRowMatches = (row, ref, timeId, riskId) => {
                const classified = agingClassifyRow(row, ref);
                if (!classified) return false;
                const [parent, child, rkey] = classified;
                const wantTime = String(timeId || "").trim();
                const wantRisk = String(riskId || "").trim();
                if (wantRisk && rkey !== wantRisk) return false;
                if (!wantTime || wantTime === "all" || wantTime === "*") return true;
                if (wantTime === parent) return true;
                if (child && wantTime === child) return true;
                return false;
            };
            const computeAging = (rows, selected, referenceRaw, _dateSource) => {
                const ref = parseDateAtNoon(referenceRaw);
                if (!ref) return { error: "Invalid reference date" };
                const dateCol = COL_TARGET;
                const cfg = pack.aging_config || { risk_columns: [], time_rows: [], over_year_rows: [] };
                const riskKeys = (cfg.risk_columns || []).map((x) => x.id);
                const overYearDefs = cfg.over_year_rows || [];
                const matrix = {};
                (cfg.time_rows || []).forEach((tr) => {
                    matrix[tr.id] = {};
                    riskKeys.forEach((rk) => (matrix[tr.id][rk] = 0));
                });
                const overMatrix = {};
                overYearDefs.forEach((tr) => {
                    overMatrix[tr.id] = {};
                    riskKeys.forEach((rk) => (overMatrix[tr.id][rk] = 0));
                });
                let skippedOther = 0;
                let unknownTime = 0;
                applyFilters(rows, selected, null).forEach((row) => {
                    const st = rowValue(row, COL_STATUS);
                    if (isClosedStatusForAging(st)) {
                        skippedOther += 1;
                        return;
                    }
                    const cdt = agingTargetDate(row);
                    if (!cdt) {
                        unknownTime += 1;
                        return;
                    }
                    const classified = agingClassifyRow(row, ref);
                    if (!classified) {
                        unknownTime += 1;
                        return;
                    }
                    const [parent, child, rkey] = classified;
                    if (!matrix[parent]) {
                        unknownTime += 1;
                        return;
                    }
                    matrix[parent][rkey] = (matrix[parent][rkey] || 0) + 1;
                    if (child && overMatrix[child]) {
                        overMatrix[child][rkey] = (overMatrix[child][rkey] || 0) + 1;
                    }
                });
                const time_rows = (cfg.time_rows || []).map((tr) => {
                    const cells = matrix[tr.id] || {};
                    const total = riskKeys.reduce((s, k) => s + (cells[k] || 0), 0);
                    return { id: tr.id, label: tr.label, cells, total };
                });
                const over_year_rows = overYearDefs.map((tr) => {
                    const cells = overMatrix[tr.id] || {};
                    const total = riskKeys.reduce((s, k) => s + (cells[k] || 0), 0);
                    return { id: tr.id, label: tr.label, cells, total };
                });
                const column_totals = {};
                riskKeys.forEach((k) => {
                    column_totals[k] = (cfg.time_rows || []).reduce((s, tr) => s + ((matrix[tr.id] || {})[k] || 0), 0);
                });
                const grand_total = riskKeys.reduce((s, k) => s + (column_totals[k] || 0), 0);
                return {
                    reference: referenceRaw.slice(0, 10),
                    date_field: dateCol,
                    date_source: "target",
                    risk_columns: cfg.risk_columns || [],
                    time_rows,
                    over_year_rows,
                    column_totals,
                    grand_total,
                    status_filter: "open_only",
                    skipped_other_status: skippedOther,
                    skipped_unknown_time: unknownTime
                };
            };
            const PLAN_STATUS_RISK_COLUMNS = (pack.plan_status_config && pack.plan_status_config.risk_columns) || [
                { id: "low", label: "منخفض", color: "#3d7a5a", text_color: "#ffffff" },
                { id: "medium", label: "متوسط", color: "#c9a227", text_color: "#1e293b" },
                { id: "high", label: "مرتفع", color: "#c24141", text_color: "#ffffff" },
                { id: "very_high", label: "مرتفع جدا", color: "#8f1d2c", text_color: "#ffffff" }
            ];
            const PLAN_STATUS_TITLE = (pack.plan_status_config && pack.plan_status_config.title) ||
                "حالة خطط المعالجة والإجراءات التصحيحية المتفق عليها مع الإدارة";
            const planScheduleBucket = (row, ref) => {
                const st = rowValue(row, COL_STATUS);
                if (isClosedStatusForAging(st)) return null;
                const t = normNFKC(st).replace(/\s+/g, " ");
                if (t.includes("تجاوز")) return "overdue";
                if (t.includes("ضمن")) return "within";
                if (!t.includes("مفتوح")) return null;
                if (ref) {
                    const cdt = agingTargetDate(row);
                    if (cdt) {
                        const cref = new Date(cdt.getFullYear(), cdt.getMonth(), cdt.getDate());
                        const rref = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate());
                        return cref >= rref ? "within" : "overdue";
                    }
                }
                return "within";
            };
            const planRiskBucket = (row) => {
                const key = agingRiskKey(agingRowRiskText(row)) || "other";
                return key === "very_low" ? "low" : key;
            };
            const planDeptId = (row) => {
                const dept = rowValue(row, "الإدارة المسؤولة");
                return !dept || dept === BLANK ? "" : dept;
            };
            const planLegalIdentity = (row, index) => {
                const legal = rowValue(row, "النص النظامي");
                if (legal && legal !== BLANK) return `legal:${legal}`;
                const system = rowValue(row, "اسم النظام");
                if (system && system !== BLANK) return `system:${system}`;
                return `row:${index}`;
            };
            const planRowMatches = (row, ref, deptId, bucket, riskId) => {
                const classified = planScheduleBucket(row, ref);
                if (!classified) return false;
                if (deptId !== null && deptId !== undefined && planDeptId(row) !== deptId) return false;
                const wantBucket = String(bucket || "").trim();
                if (wantBucket && wantBucket !== "all" && wantBucket !== "*" && classified !== wantBucket) return false;
                const wantRisk = String(riskId || "").trim();
                if (wantRisk && wantRisk !== "all" && wantRisk !== "*" && planRiskBucket(row) !== wantRisk) return false;
                return true;
            };
            const computePlanStatusReport = (rows, selected, referenceRaw) => {
                const ref = parseDateAtNoon(referenceRaw);
                const riskCols = PLAN_STATUS_RISK_COLUMNS;
                const riskKeys = riskCols.map((x) => x.id);
                const grouped = {};
                let skippedClosed = 0;
                let skippedOther = 0;
                applyFilters(rows, selected, null).forEach((row, index) => {
                    const bucket = planScheduleBucket(row, ref);
                    if (!bucket) {
                        const st = rowValue(row, COL_STATUS);
                        if (isClosedStatusForAging(st)) skippedClosed += 1;
                        else skippedOther += 1;
                        return;
                    }
                    const dept = planDeptId(row);
                    if (!grouped[dept]) {
                        grouped[dept] = {
                            id: dept,
                            label: dept || "غير محدد",
                            legalIds: new Set(),
                            within: Object.fromEntries(riskKeys.map((k) => [k, 0])),
                            overdue: Object.fromEntries(riskKeys.map((k) => [k, 0])),
                            within_total: 0,
                            overdue_total: 0
                        };
                    }
                    const slot = grouped[dept];
                    slot.legalIds.add(planLegalIdentity(row, index));
                    const rkey = planRiskBucket(row);
                    if (riskKeys.includes(rkey)) slot[bucket][rkey] += 1;
                    slot[`${bucket}_total`] += 1;
                });
                const departments = Object.keys(grouped)
                    .sort((a, b) => {
                        if (!a && b) return 1;
                        if (a && !b) return -1;
                        return String(a).localeCompare(String(b), "ar");
                    })
                    .map((dept) => {
                        const slot = grouped[dept];
                        return {
                            id: slot.id,
                            label: slot.label,
                            legal_text_count: slot.legalIds.size,
                            within: slot.within,
                            overdue: slot.overdue,
                            within_total: slot.within_total,
                            overdue_total: slot.overdue_total
                        };
                    });
                const totals = {
                    legal_text_count: departments.reduce((s, d) => s + d.legal_text_count, 0),
                    within: Object.fromEntries(riskKeys.map((k) => [k, 0])),
                    overdue: Object.fromEntries(riskKeys.map((k) => [k, 0])),
                    within_total: 0,
                    overdue_total: 0
                };
                departments.forEach((d) => {
                    riskKeys.forEach((k) => {
                        totals.within[k] += d.within[k] || 0;
                        totals.overdue[k] += d.overdue[k] || 0;
                    });
                    totals.within_total += d.within_total;
                    totals.overdue_total += d.overdue_total;
                });
                return {
                    title: PLAN_STATUS_TITLE,
                    reference: String(referenceRaw || "").slice(0, 10),
                    risk_columns: riskCols,
                    departments,
                    totals,
                    department_count: departments.length,
                    open_total: totals.within_total + totals.overdue_total,
                    skipped_closed: skippedClosed,
                    skipped_other: skippedOther
                };
            };
            const PROGRAM_STATUS_LEVELS = (pack.program_status_config && pack.program_status_config.levels) || [
                { id: "green", label: "أخضر", color: "#3d7a5a", text: "البرنامج يعمل ضمن المستويات المقبولة للمخاطر، ولا توجد قضايا التزام جوهرية." },
                { id: "yellow", label: "أصفر", color: "#c9a227", text: "توجد قضايا أو مخاطر تتطلب متابعة، لكنها لا تشكل تهديداً جوهرياً في الوقت الحالي." },
                { id: "red", label: "أحمر", color: "#c24141", text: "توجد قضايا جوهرية أو تجاوزات تنظيمية تستدعي تدخلاً عاجلاً من اللجنة والإدارة." }
            ];
            const PROGRAM_STATUS_TITLE = (pack.program_status_config && pack.program_status_config.title) || "الحالة العامة لبرنامج الالتزام";
            const PROGRAM_STATUS_GUIDE = (pack.program_status_config && pack.program_status_config.guide) || "دليل تصنيف الحالة العامة للبرنامج";
            const programStatusFromRow = (row) => {
                for (const key of Object.keys(row || {})) {
                    const k = String(key || "").normalize("NFKC");
                    if (k.includes("حالة الالتزام") && k.includes("إدارة الالتزام")) {
                        const v = rowValue(row, key);
                        if (v && v !== BLANK) return v;
                    }
                }
                return rowValue(row, "حالة الالتزام بالمتطلبات");
            };
            const programComplianceBucket = (statusText) => {
                const t = normNFKC(statusText).replace(/\s+/g, " ").trim();
                if (!t || t === BLANK) return null;
                const compact = t.replace(/\s/g, "");
                if (compact.includes("غيرملتزم") || /غير\s*ملتزم/.test(t)) return "noncompliant";
                if (t.includes("جزئي")) return "partial";
                if (t.includes("ملتزم")) return "compliant";
                return null;
            };
            const programRowMatches = (row, deptId, bucket) => {
                const classified = programComplianceBucket(programStatusFromRow(row));
                if (!classified) return false;
                if (deptId !== null && deptId !== undefined && planDeptId(row) !== deptId) return false;
                const want = String(bucket || "").trim();
                if (want && want !== "all" && want !== "*" && classified !== want) return false;
                return true;
            };
            const computeProgramStatusReport = (rows, selected) => {
                const grouped = {};
                let skippedOther = 0;
                applyFilters(rows, selected, null).forEach((row, index) => {
                    const bucket = programComplianceBucket(programStatusFromRow(row));
                    if (!bucket) {
                        skippedOther += 1;
                        return;
                    }
                    const dept = planDeptId(row);
                    if (!grouped[dept]) {
                        grouped[dept] = {
                            id: dept,
                            label: dept || "غير محدد",
                            legalIds: new Set(),
                            compliantIds: new Set(),
                            noncompliantIds: new Set(),
                            partialIds: new Set()
                        };
                    }
                    const identity = planLegalIdentity(row, index);
                    const slot = grouped[dept];
                    slot.legalIds.add(identity);
                    slot[`${bucket}Ids`].add(identity);
                });
                const departments = Object.keys(grouped)
                    .sort((a, b) => {
                        if (!a && b) return 1;
                        if (a && !b) return -1;
                        return String(a).localeCompare(String(b), "ar");
                    })
                    .map((dept) => {
                        const slot = grouped[dept];
                        return {
                            id: slot.id,
                            label: slot.label,
                            legal_text_count: slot.legalIds.size,
                            compliant: slot.compliantIds.size,
                            noncompliant: slot.noncompliantIds.size,
                            partial: slot.partialIds.size
                        };
                    });
                const totals = {
                    legal_text_count: departments.reduce((s, d) => s + d.legal_text_count, 0),
                    compliant: departments.reduce((s, d) => s + d.compliant, 0),
                    noncompliant: departments.reduce((s, d) => s + d.noncompliant, 0),
                    partial: departments.reduce((s, d) => s + d.partial, 0)
                };
                let overallId = "green";
                if (totals.noncompliant > 0) overallId = "red";
                else if (totals.partial > 0) overallId = "yellow";
                const overall = PROGRAM_STATUS_LEVELS.find((item) => item.id === overallId) || PROGRAM_STATUS_LEVELS[0];
                return {
                    title: PROGRAM_STATUS_TITLE,
                    guide: PROGRAM_STATUS_GUIDE,
                    levels: PROGRAM_STATUS_LEVELS,
                    overall,
                    departments,
                    totals,
                    department_count: departments.length,
                    skipped_other: skippedOther
                };
            };
            const parseFetch = (url) => {
                if (url.includes("://")) {
                    const u = new URL(url);
                    return { path: u.pathname, sp: u.searchParams };
                }
                const [path, q = ""] = url.split("?");
                return { path, sp: new URLSearchParams(q) };
            };
            const jsonResponse = (obj, code = 200) =>
                Promise.resolve(new Response(JSON.stringify(obj), { status: code, headers: { "Content-Type": "application/json" } }));
            const isBlankCell = (v) => {
                if (v === undefined || v === null || v === 0) return true;
                const s = String(v).trim();
                if (!s || s === BLANK) return true;
                const t = s.toLowerCase();
                return s === "0" || s === "0.0" || t === "nan" || t === "none" || t === "null" || t === "n/a" || t === "-" || t === "—";
            };
            const rowHasRecord = (row) => {
                const keys = [
                    COL_STATUS, COL_INHERENT, COL_RESIDUAL, COL_YEAR, COL_TARGET, COL_MODIFIED,
                    "نتائج التقييم خلال السنة الحالية",
                    "تاريخ التصحيح السنوي المستهدف", "تاريخ التصحيح المستهدف - الربعي",
                    "تاريخ التصحيح السنوي الفعلي", "تاريخ التصحيح الفعلي - الربعي",
                    "النص النظامي", "اسم النظام", "اللائحة", "المشرع",
                    "حالة الالتزام بالمتطلبات", "فئة الضوابط الرقابية",
                    "الخطة التصحيحية", "ملاحظات الإدارة", "البنود/المتطلبات غير الملتزم بها",
                    "مالك المهمة / مالك الإجراء", "الشخص المسؤول",
                    COL_FINAL_PREV, COL_FINAL_CURR
                ];
                return keys.some((col) => !isBlankCell(row[col]));
            };
            const rows = (pack.rows || [])
                .map((row) => enrichRowDateDims(enrichRowYear({ ...row })))
                .filter(rowHasRecord);
            const OFFLINE_SERVER_BASE =
                localStorage.getItem("excelArabicServerBase") ||
                "http://127.0.0.1:8765";
            const origFetch = window.fetch.bind(window);
            window.fetch = function (input, init) {
                const url = typeof input === "string" ? input : input.url;
                const isArApi = /\/ar-api(\/|$|\?)/.test(url || "");
                if (!url || (!url.includes("/api/") && !isArApi)) return origFetch(input, init);
                const { path, sp } = parseFetch(url);
                if (path.includes("/ar-api/summary") || path.endsWith("/api/summary")) {
                    return jsonResponse(buildSummary(rows, selectedFromParams(sp)));
                }
                if (path.includes("/ar-api/records") || path.endsWith("/api/records") || (/\/assessment-forms(\/|$|\?)/.test(path) && !path.includes("export-assessment"))) {
                    let filtered = applyFilters(rows, selectedFromParams(sp), null);
                    const agingTime = (sp.get("aging_time") || "").trim();
                    const agingRisk = (sp.get("aging_risk") || "").trim();
                    const agingRef = parseDateAtNoon((sp.get("reference") || "").trim());
                    if (agingTime || agingRisk) {
                        filtered = agingRef
                            ? filtered.filter((row) => agingRowMatches(row, agingRef, agingTime || "all", agingRisk))
                            : [];
                    }
                    const planBucket = (sp.get("plan_bucket") || "").trim();
                    const planRisk = (sp.get("plan_risk") || "").trim();
                    if (sp.has("plan_dept") || planBucket || planRisk) {
                        const planRef = parseDateAtNoon((sp.get("reference") || "").trim());
                        let deptId = null;
                        if (sp.has("plan_dept")) {
                            const rawDept = String(sp.get("plan_dept") || "").trim();
                            deptId = !rawDept || rawDept === "__none__" || rawDept === "(blank)" ? "" : rawDept;
                        }
                        filtered = filtered.filter((row) => planRowMatches(row, planRef, deptId, planBucket, planRisk));
                    }
                    const programStatus = (sp.get("program_status") || "").trim();
                    if (sp.has("program_dept") || programStatus) {
                        let deptId = null;
                        if (sp.has("program_dept")) {
                            const rawDept = String(sp.get("program_dept") || "").trim();
                            deptId = !rawDept || rawDept === "__none__" || rawDept === "(blank)" ? "" : rawDept;
                        }
                        filtered = filtered.filter((row) => programRowMatches(row, deptId, programStatus));
                    }
                    const finalChange = ["1", "true", "yes"].includes(String(sp.get("final_status_change") || "").trim().toLowerCase());
                    const assessmentNew = ["1", "true", "yes"].includes(String(sp.get("assessment_new") || "").trim().toLowerCase());
                    const isFullyCompliant = (value) => {
                        const t = String(value || "").normalize("NFKC").replace(/\s+/g, " ").trim();
                        if (!t || t === BLANK) return false;
                        const compact = t.replace(/\s/g, "");
                        if (compact.includes("غيرملتزم") || /غير\s*ملتزم/.test(t)) return false;
                        if (t.includes("جزئي")) return false;
                        return t.includes("ملتزم");
                    };
                    if (finalChange) {
                        filtered = filtered.filter((row) => {
                            const prev = rowValue(row, COL_FINAL_PREV);
                            const curr = rowValue(row, COL_FINAL_CURR);
                            return isFullyCompliant(prev) && !isFullyCompliant(curr);
                        });
                    }
                    const headerHas = (key, needles) => needles.every((n) => String(key || "").normalize("NFKC").includes(n));
                    const valueByNeedles = (row, needles) => {
                        for (const key of Object.keys(row || {})) {
                            if (!headerHas(key, needles)) continue;
                            const v = rowValue(row, key);
                            if (v && v !== BLANK) return v;
                        }
                        return "";
                    };
                    const complianceMgmtFromRow = (row) => {
                        let raw = valueByNeedles(row, ["حالة الالتزام", "إدارة الالتزام"]);
                        if (!raw || raw === BLANK) raw = rowValue(row, "حالة الالتزام بالمتطلبات");
                        return !raw || raw === BLANK ? "" : raw;
                    };
                    const isNewDetailed = (row) => {
                        let raw = rowValue(row, COL_DETAILED_REPORT);
                        if (!raw || raw === BLANK) raw = valueByNeedles(row, ["التقرير التفصيلي", "عدم الالتزام"]);
                        return String(raw || "").trim().toLowerCase() === "new";
                    };
                    const isAssessmentFormsApi = /\/assessment-forms(\/|$|\?)/.test(path) && !path.includes("export-assessment");
                    if (assessmentNew || isAssessmentFormsApi) {
                        filtered = filtered.filter(isNewDetailed);
                    }
                    const formatFormDate = (raw) => {
                        const dt = parseDateAtNoon(raw);
                        if (dt) {
                            const y = dt.getFullYear();
                            const m = String(dt.getMonth() + 1).padStart(2, "0");
                            const d = String(dt.getDate()).padStart(2, "0");
                            return `${y}-${m}-${d}`;
                        }
                        const s = String(raw || "").trim();
                        if (!s || s === BLANK) return "";
                        return s;
                    };
                    const formFromRow = (row) => {
                        const cell = (v) => (!v || v === BLANK ? "" : String(v).trim());
                        let article = rowValue(row, "رقم المادة");
                        if (!article || article === BLANK) article = valueByNeedles(row, ["رقم المادة"]);
                        let riskNote = rowValue(row, "مخاطر عدم الالتزام");
                        if (!riskNote || riskNote === BLANK) riskNote = valueByNeedles(row, ["مخاطر عدم الالتزام"]);
                        let planRaw = valueByNeedles(row, ["الإجراء التصحيحي"]);
                        if (!planRaw || planRaw === BLANK) {
                            planRaw = rowValue(row, "الخطة التصحيحية");
                        }
                        if (!planRaw || planRaw === BLANK) {
                            planRaw = valueByNeedles(row, ["الإجراء", "الخطة"]);
                        }
                        if (!planRaw || planRaw === BLANK) {
                            for (const key of Object.keys(row || {})) {
                                const k = String(key || "").normalize("NFKC");
                                if (k.includes("حالة") && k.includes("الخطة التصحيحية")) continue;
                                if (k.includes("مالك")) continue;
                                if (k.includes("الإجراء التصحيحي") || k.includes("الخطة التصحيحية") || k.trim() === "الإجراء") {
                                    const v = rowValue(row, key);
                                    if (v && v !== BLANK) {
                                        planRaw = v;
                                        break;
                                    }
                                }
                            }
                        }
                        let targetRaw = rowValue(row, COL_TARGET);
                        if (!targetRaw || targetRaw === BLANK) {
                            targetRaw = valueByNeedles(row, ["تاريخ التصحيح المستهدف"]);
                        }
                        return {
                            legislator: cell(rowValue(row, "المشرع")),
                            system_name: cell(rowValue(row, "اسم النظام")),
                            authority: cell(rowValue(row, "الهيئة التابعة")),
                            regulation: cell(rowValue(row, "اللائحة")),
                            inherent: cell(rowValue(row, COL_INHERENT)),
                            compliance_status: cell(rowValue(row, "حالة الالتزام بالمتطلبات")),
                            article_no: cell(article),
                            legal_text: cell(rowValue(row, "النص النظامي")),
                            noncompliant_items: cell(rowValue(row, "البنود/المتطلبات غير الملتزم بها")),
                            noncompliance_risk: cell(riskNote),
                            corrective_plan: cell(planRaw),
                            department: cell(rowValue(row, "الإدارة المسؤولة")),
                            target_date: formatFormDate(targetRaw),
                            plan_status: cell(rowValue(row, COL_STATUS))
                        };
                    };
                    if (isAssessmentFormsApi) {
                        const forms = filtered.map(formFromRow);
                        return jsonResponse({ total: forms.length, truncated: false, forms });
                    }
                    const recLimit = assessmentNew ? 2000 : 400;
                    const records = filtered.slice(0, recLimit).map((row) => {
                        const legal = rowValue(row, "النص النظامي");
                        const system = rowValue(row, "اسم النظام");
                        let rating = rowValue(row, COL_INHERENT);
                        if (rating === BLANK) rating = rowValue(row, COL_RESIDUAL);
                        const observation = legal !== BLANK ? legal : system;
                        const dept = rowValue(row, "الإدارة المسؤولة");
                        const status = rowValue(row, COL_STATUS);
                        const selected = selectedFromParams(sp);
                        const actualActive = (selected[PARAM_TO_COL.actual_annual] || []).length || (selected[PARAM_TO_COL.actual_quarterly] || []).length;
                        const targetActive = (selected[PARAM_TO_COL.target_annual] || []).length || (selected[PARAM_TO_COL.target_quarterly] || []).length || (selected[PARAM_TO_COL.year] || []).length;
                        const qCols = actualActive && !targetActive
                            ? [PARAM_TO_COL.actual_quarterly, PARAM_TO_COL.target_quarterly]
                            : [PARAM_TO_COL.target_quarterly, PARAM_TO_COL.actual_quarterly];
                        let quarter = "";
                        for (const col of qCols) {
                            const m = String(rowValue(row, col) || "").match(/Q\s*([1-4])/i);
                            if (m) { quarter = "Q" + m[1]; break; }
                        }
                        if (!quarter) {
                            const dateCols = actualActive && !targetActive
                                ? ["تاريخ التصحيح الفعلي", COL_MODIFIED, COL_TARGET]
                                : [COL_TARGET, "تاريخ التصحيح الفعلي", COL_MODIFIED];
                            for (const col of dateCols) {
                                const raw = rowValue(row, col);
                                const m = String(raw || "").match(/Q\s*([1-4])/i);
                                if (m) { quarter = "Q" + m[1]; break; }
                                const dt = parseDateAtNoon(raw);
                                if (dt) {
                                    quarter = "Q" + String(Math.floor(dt.getMonth() / 3) + 1);
                                    break;
                                }
                            }
                        }
                        const rec = {
                            observation: observation === BLANK ? "—" : observation,
                            legal_text: legal === BLANK ? "" : legal,
                            system_name: system === BLANK ? "" : system,
                            rating: rating === BLANK ? "" : rating,
                            department: dept === BLANK ? "" : dept,
                            legislator: rowValue(row, "المشرع") === BLANK ? "" : rowValue(row, "المشرع"),
                            article_no: (() => {
                                let article = rowValue(row, "رقم المادة");
                                if (!article || article === BLANK) article = valueByNeedles(row, ["رقم المادة"]);
                                return !article || article === BLANK ? "" : article;
                            })(),
                            status: status === BLANK ? "" : status,
                            compliance_mgmt: complianceMgmtFromRow(row),
                            quarter,
                            final_prev: rowValue(row, COL_FINAL_PREV) === BLANK ? "" : rowValue(row, COL_FINAL_PREV),
                            final_curr: rowValue(row, COL_FINAL_CURR) === BLANK ? "" : rowValue(row, COL_FINAL_CURR)
                        };
                        if (assessmentNew) {
                            rec.form = formFromRow(row);
                        }
                        return rec;
                    });
                    return jsonResponse({
                        total: filtered.length,
                        truncated: filtered.length > recLimit,
                        records
                    });
                }
                if (path.includes("/api/legal-text-row-images") || path.includes("/ar-api/legal-text-row-images")) {
                    const excelRow = String(sp.get("excel_row") || "").trim();
                    const images = (pack.row_images && pack.row_images[excelRow]) || [];
                    return jsonResponse({ images });
                }
                if (path.includes(arApiUrl('/send-legal-text-email'))) {
                    const target = `${OFFLINE_SERVER_BASE.replace(/\/+$/, "")}/api/send-legal-text-email`;
                    const forwardedInit = Object.assign({}, init || {}, { credentials: "omit" });
                    return origFetch(target, forwardedInit);
                }
                if (path.includes("/ar-api/legal-text-details") || path.includes(arApiUrl("/legal-text-details"))) {
                    let txt = (sp.get("text") || "").trim();
                    if (!txt && init?.body && typeof init.body === "string") {
                        try { txt = JSON.parse(init.body).text || ""; } catch {}
                    }
                    let rec = legalDetailsFromRows(txt);
                    if (!rec && (pack.legal_details || {})[txt]) {
                        const ld = (pack.legal_details || {})[txt];
                        const fields = ld.fields || [];
                        const emf = fields.find((f) => String(f.label || "").toLowerCase().includes("email"));
                        rec = {
                            legal_text: txt,
                            excel_row: ld.excel_row || 0,
                            picked_row_index: 0,
                            recipient_email: (emf && emf.value) || "",
                            fields,
                            images: ld.images || []
                        };
                    }
                    return rec ? jsonResponse(rec) : jsonResponse({ error: "Not found" }, 404);
                }
                if (path.includes("/api/audit-plan-panel") || path.includes("/ar-api/audit-plan-panel")) {
                    const selected = selectedFromParams(sp);
                    const filtered = applyFilters(rows, selected, null);
                    const columns = (pack.audit_columns || []).map((col) => {
                        const counts = {};
                        let nonNull = 0;
                        filtered.forEach((r) => {
                            const v = rowValue(r, col);
                            counts[v] = (counts[v] || 0) + 1;
                            if (v !== BLANK) nonNull += 1;
                        });
                        const ordered = Object.entries(counts).sort((a, b) => b[1] - a[1]);
                        return { name: col, entries: ordered.slice(0, 80).map(([label, count]) => ({ label, count })), truncated: ordered.length > 80, distinct: ordered.length, non_null: nonNull };
                    });
                    return jsonResponse({ total_rows: filtered.length, columns });
                }
                if (path.includes("/api/aging-summary") || path.includes("/ar-api/aging-summary")) {
                    const ref = (sp.get("reference") || "").trim();
                    const dateSource = ((sp.get("aging_date_source") || "target") + "").toLowerCase();
                    if (!ref) return jsonResponse({ error: "Missing reference date" }, 400);
                    const out = computeAging(rows, selectedFromParams(sp), ref, dateSource === "modified" ? "modified" : "target");
                    if (out.error) return jsonResponse({ error: out.error }, 400);
                    return jsonResponse(out);
                }
                if (path.includes("/api/plan-status-summary") || path.includes("/ar-api/plan-status-summary")) {
                    const ref = (sp.get("reference") || "").trim();
                    return jsonResponse(computePlanStatusReport(rows, selectedFromParams(sp), ref));
                }
                if (path.includes("/api/program-status-summary") || path.includes("/ar-api/program-status-summary")) {
                    return jsonResponse(computeProgramStatusReport(rows, selectedFromParams(sp)));
                }
                return origFetch(input, init);
            };
        })();


        const state = {
            control_category: [],
            inherent: [],
            residual: [],
            status: [],
            year: [],
            assessment_year: [],
            target_annual: [],
            target_quarterly: [],
            actual_annual: [],
            actual_quarterly: [],
            department: [],
            legislator: [],
            compliance_status: [],
            system_name: [],
            authority: [],
            regulation: [],
            legal_text: [],
            subsidiary_company: [],
            holding_company: []
        };
        let activeFieldKey = "";

        function buildFilterQueryString(st) {
            const qs = new URLSearchParams();
            Object.entries(st).forEach(([key, vals]) => {
                if (!Array.isArray(vals)) {
                    return;
                }
                vals.forEach((v) => {
                    if (v !== "" && v != null) {
                        qs.append(key, v);
                    }
                });
            });
            return qs;
        }

        const BRAND_LOGO_CODES = new Set(["nat", "aum", "saco", "autostar", "btc"]);

        function resolveMainBrandLogoCode() {
            const pack = getSnapshotPack();
            if (!pack || pack.default_brand_code == null || pack.default_brand_code === "") {
                return null;
            }
            const code = String(pack.default_brand_code).trim().toLowerCase();
            return code || null;
        }

        function normalizeBrandLogoKey(raw) {
            const code = String(raw || "").trim();
            if (!code) {
                return "";
            }
            const lower = code.toLowerCase();
            return BRAND_LOGO_CODES.has(lower) ? lower : lower;
        }

        function lookupBrandLogoUri(logos, code) {
            if (!logos || !code) {
                return null;
            }
            const key = String(code).trim();
            return logos[key] || logos[key.toLowerCase()] || logos[key.toUpperCase()] || null;
        }

        function resolveSelectedSingleBrandCode() {
            const stateKey = companyBrandStateKey();
            const values = state[stateKey];
            if (!Array.isArray(values) || values.length !== 1) {
                return null;
            }
            const normalized = normalizeBrandLogoKey(values[0]);
            return normalized || null;
        }

        function resolveActiveBrandLogoCode() {
            return resolveSelectedSingleBrandCode() || resolveMainBrandLogoCode();
        }

        function hasVisibleBrandLogo(img) {
            const src = img.getAttribute("src") || "";
            return Boolean(src) && !img.hidden;
        }

        function clearBrandLogo() {
            const img = document.getElementById("headerLogo");
            if (!img) {
                return;
            }
            if (brandLogoObjectUrl) {
                URL.revokeObjectURL(brandLogoObjectUrl);
                brandLogoObjectUrl = null;
            }
            img.hidden = true;
            img.removeAttribute("src");
        }

        let brandLogoObjectUrl = null;
        let lastBrandLogoCode = null;

        function getSnapshotPack() {
            const packEl = document.getElementById("snapshot-pack");
            if (!packEl) {
                return null;
            }
            try {
                return JSON.parse(packEl.textContent || "{}");
            } catch {
                return null;
            }
        }

        function resolveSnapshotBrandLogoDataUrl() {
            const pack = getSnapshotPack();
            if (!pack || !pack.brand_logos) {
                return null;
            }
            const activeCode = resolveActiveBrandLogoCode();
            const mainCode = resolveMainBrandLogoCode();
            if (!activeCode) {
                return null;
            }
            return (
                lookupBrandLogoUri(pack.brand_logos, activeCode) ||
                (activeCode !== mainCode ? lookupBrandLogoUri(pack.brand_logos, mainCode) : null)
            );
        }

        async function updateBrandLogo() {
            const img = document.getElementById("headerLogo");
            if (!img) {
                syncReportBrandLogos();
                return;
            }
            const activeCode = resolveActiveBrandLogoCode();
            const mainCode = resolveMainBrandLogoCode();
            if (!activeCode && !mainCode) {
                if (!hasVisibleBrandLogo(img)) {
                    clearBrandLogo();
                }
                lastBrandLogoCode = null;
                syncReportBrandLogos();
                return;
            }
            const code = activeCode || mainCode;
            const embeddedLogo = resolveSnapshotBrandLogoDataUrl();
            if (embeddedLogo) {
                if (brandLogoObjectUrl) {
                    URL.revokeObjectURL(brandLogoObjectUrl);
                    brandLogoObjectUrl = null;
                }
                img.src = embeddedLogo;
                img.hidden = false;
                lastBrandLogoCode = code;
                syncReportBrandLogos();
                return;
            }
            if (lastBrandLogoCode === code && hasVisibleBrandLogo(img)) {
                syncReportBrandLogos();
                return;
            }
            const codesToTry = code === mainCode || !mainCode ? [code] : [code, mainCode];
            for (const tryCode of codesToTry) {
                if (brandLogoObjectUrl) {
                    URL.revokeObjectURL(brandLogoObjectUrl);
                    brandLogoObjectUrl = null;
                }
                const url = `${arApiUrl('/brand-logo')}?code=${encodeURIComponent(tryCode)}`;
                try {
                    const response = await fetch(url, { credentials: "same-origin" });
                    if (!response.ok || response.status === 204) {
                        continue;
                    }
                    const blob = await response.blob();
                    if (!blob.size) {
                        continue;
                    }
                    brandLogoObjectUrl = URL.createObjectURL(blob);
                    img.src = brandLogoObjectUrl;
                    img.hidden = false;
                    lastBrandLogoCode = tryCode;
                    syncReportBrandLogos();
                    return;
                } catch {
                    continue;
                }
            }
            syncReportBrandLogos();
        }

        function currentBrandLogoSrc() {
            const img = document.getElementById("headerLogo");
            if (img && !img.hidden && img.getAttribute("src")) {
                return img.src;
            }
            return resolveSnapshotBrandLogoDataUrl() || "";
        }

        function syncReportBrandLogos() {
            const src = currentBrandLogoSrc();
            document.querySelectorAll(".report-brand-logo").forEach((el) => {
                if (!src) {
                    el.hidden = true;
                    el.removeAttribute("src");
                    return;
                }
                el.src = src;
                el.hidden = false;
            });
        }

        function toggleFilterValue(arr, value) {
            const i = arr.indexOf(value);
            if (i >= 0) {
                arr.splice(i, 1);
            } else {
                arr.push(value);
            }
        }

        let lastTileDrillKey = "";
        let recordListRows = [];
        let recordListShowFinalChange = false;
        let recordListShowAssessmentNew = false;
        let recordListSkipQuarters = false;
        let recordListShowYearCompliance = false;
        let assessmentGeneratedForms = [];

        function recordListColSpan() {
            if (recordListShowFinalChange) {
                return 7;
            }
            if (recordListShowAssessmentNew) {
                return 5;
            }
            if (recordListShowYearCompliance) {
                return 4;
            }
            return 3;
        }

        function recordListShowLegislatorCols() {
            return recordListShowFinalChange || recordListShowAssessmentNew;
        }

        function syncRecordListHead() {
            document.querySelectorAll(".record-th-legislator, .record-th-article").forEach((th) => {
                th.hidden = !recordListShowLegislatorCols();
            });
            document.querySelectorAll(".record-th-final-prev, .record-th-final-curr").forEach((th) => {
                th.hidden = !recordListShowFinalChange;
            });
            document.querySelectorAll(".record-th-compliance").forEach((th) => {
                th.hidden = !recordListShowYearCompliance;
            });
            const modal = document.getElementById("recordListModal");
            if (modal) {
                modal.classList.toggle("is-final-report", recordListShowFinalChange);
                modal.classList.toggle("is-assessment-report", recordListShowAssessmentNew);
                modal.classList.toggle("is-year-plan", recordListShowYearCompliance);
            }
            const gen = document.getElementById("assessmentGenerateBtn");
            if (gen) {
                gen.hidden = !recordListShowAssessmentNew;
            }
            const annualWord = document.getElementById("annualTrackingWordBtn");
            if (annualWord) {
                annualWord.hidden = !recordListShowLegislatorCols();
            }
            const metaEl = document.getElementById("recordListMeta");
            if (metaEl) {
                metaEl.hidden = recordListShowLegislatorCols();
                if (recordListShowLegislatorCols()) {
                    metaEl.textContent = "";
                }
            }
            document.querySelectorAll(".record-list-kicker").forEach((el) => {
                el.hidden = recordListShowLegislatorCols();
            });
        }

        function isRecordListOpen() {
            const el = document.getElementById("recordListModal");
            return !!(el && el.style.display === "flex");
        }

        function closeRecordList() {
            const el = document.getElementById("recordListModal");
            if (el) {
                el.style.display = "none";
            }
            const search = document.getElementById("recordListSearch");
            if (search) {
                search.value = "";
            }
            recordListShowFinalChange = false;
            recordListShowAssessmentNew = false;
            recordListShowYearCompliance = false;
            recordListSkipQuarters = false;
            syncRecordListHead();
            const finalToggle = document.getElementById("finalStatusToggle");
            if (finalToggle) {
                finalToggle.checked = false;
            }
            const assessmentToggle = document.getElementById("assessmentNewToggle");
            if (assessmentToggle) {
                assessmentToggle.checked = false;
            }
        }

        function appendRecordListRow(body, row) {
            const tr = document.createElement("tr");
            tr.tabIndex = 0;
            tr.setAttribute("role", "button");
            const obs = document.createElement("td");
            obs.textContent = row.observation || "—";
            if (row.system_name && row.legal_text && row.system_name !== row.observation) {
                const sub = document.createElement("div");
                sub.style.fontWeight = "600";
                sub.style.fontSize = "12px";
                sub.style.color = "#64748b";
                sub.style.marginTop = "4px";
                sub.textContent = row.system_name;
                obs.appendChild(sub);
            }
            const risk = document.createElement("td");
            const pill = document.createElement("span");
            const vis = residualRiskSegmentStyle(row.rating || "(blank)");
            pill.className = "record-risk-pill";
            pill.textContent = row.rating || "—";
            pill.style.background = vis.background;
            pill.style.color = vis.color;
            risk.appendChild(pill);
            const dept = document.createElement("td");
            dept.textContent = row.department || "—";
            if (recordListShowLegislatorCols()) {
                const legislator = document.createElement("td");
                legislator.textContent = row.legislator || "—";
                const article = document.createElement("td");
                article.textContent = row.article_no || "—";
                tr.appendChild(legislator);
                tr.appendChild(article);
            }
            tr.appendChild(obs);
            tr.appendChild(risk);
            tr.appendChild(dept);
            if (recordListShowYearCompliance) {
                const compliance = document.createElement("td");
                compliance.textContent = row.compliance_mgmt || "—";
                tr.appendChild(compliance);
            }
            if (recordListShowFinalChange) {
                const prev = document.createElement("td");
                prev.textContent = row.final_prev || "—";
                const curr = document.createElement("td");
                curr.textContent = row.final_curr || "—";
                curr.style.fontWeight = "800";
                tr.appendChild(prev);
                tr.appendChild(curr);
            }
            const open = () => {
                if (row.legal_text) {
                    openLegalDetails(row.legal_text);
                }
            };
            tr.addEventListener("click", open);
            tr.addEventListener("keydown", (ev) => {
                if (ev.key === "Enter" || ev.key === " ") {
                    ev.preventDefault();
                    open();
                }
            });
            body.appendChild(tr);
        }

        function appendQuarterSection(body, label, rows) {
            const header = document.createElement("tr");
            header.className = "record-quarter-row";
            const cell = document.createElement("td");
            cell.colSpan = recordListColSpan();
            const inner = document.createElement("div");
            inner.className = "record-quarter-inner";
            const title = document.createElement("span");
            title.className = "record-quarter-label";
            title.textContent = label;
            const count = document.createElement("span");
            count.className = "record-quarter-count";
            count.textContent = toEnglishNumber(rows.length);
            inner.appendChild(title);
            inner.appendChild(count);
            cell.appendChild(inner);
            header.appendChild(cell);
            body.appendChild(header);
            if (!rows.length) {
                const empty = document.createElement("tr");
                empty.className = "record-quarter-empty";
                const emptyCell = document.createElement("td");
                emptyCell.colSpan = recordListColSpan();
                emptyCell.textContent = "لا توجد سجلات في هذا الربع";
                empty.appendChild(emptyCell);
                body.appendChild(empty);
                return;
            }
            rows.forEach((row) => appendRecordListRow(body, row));
        }

        function renderRecordListRows(query) {
            const body = document.getElementById("recordListBody");
            const empty = document.getElementById("recordListEmpty");
            if (!body) {
                return;
            }
            const q = String(query || "").trim().toLowerCase();
            const list = recordListRows.filter((row) => {
                if (!q) {
                    return true;
                }
                const blob = `${row.observation || ""} ${row.department || ""} ${row.legislator || ""} ${row.article_no || ""} ${row.rating || ""} ${row.system_name || ""} ${row.quarter || ""} ${row.compliance_mgmt || ""} ${row.final_prev || ""} ${row.final_curr || ""}`.toLowerCase();
                return blob.includes(q);
            });
            body.innerHTML = "";
            if (empty) {
                empty.hidden = list.length > 0;
            }
            if (!list.length) {
                return;
            }
            if (recordListShowFinalChange || recordListShowAssessmentNew || recordListSkipQuarters) {
                list.forEach((row) => appendRecordListRow(body, row));
                return;
            }
            const grouped = { Q1: [], Q2: [], Q3: [], Q4: [], none: [] };
            list.forEach((row) => {
                const key = String(row.quarter || "").toUpperCase();
                if (grouped[key]) {
                    grouped[key].push(row);
                } else {
                    grouped.none.push(row);
                }
            });
            ["Q1", "Q2", "Q3", "Q4"].forEach((label) => {
                appendQuarterSection(body, label, grouped[label]);
            });
            if (grouped.none.length) {
                appendQuarterSection(body, "بدون ربع", grouped.none);
            }
        }

        async function openRecordList(title, extraParams) {
            const modal = document.getElementById("recordListModal");
            const titleEl = document.getElementById("recordListTitle");
            const metaEl = document.getElementById("recordListMeta");
            if (titleEl) {
                titleEl.textContent = title || "السجلات";
            }
            if (metaEl && !(extraParams && (extraParams.assessment_new || extraParams.final_status_change))) {
                metaEl.textContent = "جاري التحميل…";
            }
            if (modal) {
                modal.style.display = "flex";
            }
            syncReportBrandLogos();
            recordListShowFinalChange = Boolean(extraParams && extraParams.final_status_change);
            recordListShowAssessmentNew = Boolean(extraParams && extraParams.assessment_new);
            recordListSkipQuarters = Boolean(extraParams && extraParams.skip_quarters);
            recordListShowYearCompliance = Boolean(extraParams && extraParams.year_compliance);
            const finalToggle = document.getElementById("finalStatusToggle");
            if (finalToggle && !recordListShowFinalChange) {
                finalToggle.checked = false;
            }
            const assessmentToggle = document.getElementById("assessmentNewToggle");
            if (assessmentToggle && !recordListShowAssessmentNew) {
                assessmentToggle.checked = false;
            }
            syncRecordListHead();
            try {
                const qs = buildFilterQueryString(state);
                if (extraParams && typeof extraParams === "object") {
                    Object.entries(extraParams).forEach(([key, val]) => {
                        if (key === "skip_quarters" || key === "year_compliance") {
                            return;
                        }
                        if (val !== "" && val != null) {
                            qs.set(key, String(val));
                        }
                    });
                }
                const response = await fetch(`${arApiUrl("/records")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                const data = await response.json();
                recordListRows = data.records || [];
                const total = Number(data.total || recordListRows.length);
                if (metaEl) {
                    if (recordListShowFinalChange || recordListShowAssessmentNew) {
                        metaEl.textContent = "";
                    } else {
                        const shown = toEnglishNumber(recordListRows.length);
                        const all = toEnglishNumber(total);
                        metaEl.textContent = data.truncated
                            ? `${shown} من ${all} سجل — انقر صفاً لفتح التفاصيل`
                            : `${all} سجل — انقر صفاً لفتح التفاصيل`;
                    }
                }
                renderRecordListRows(document.getElementById("recordListSearch")?.value);
            } catch (_err) {
                recordListRows = [];
                if (metaEl) {
                    metaEl.textContent = "تعذر تحميل السجلات.";
                }
                renderRecordListRows("");
            }
        }

        function escapeAssessmentHtml(value) {
            return String(value ?? "")
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;");
        }

        function assessmentFormPageHtml(form) {
            const v = (key) => escapeAssessmentHtml((form && form[key]) || "");
            const logoSrc = currentBrandLogoSrc();
            const logoBlock = logoSrc
                ? `<img class="report-brand-logo" src="${escapeAssessmentHtml(logoSrc)}" alt="">`
                : "";
            return `
<article class="assessment-form-page">
  <header class="assessment-form-brand">${logoBlock}<span class="assessment-form-brand-label">إدارة الالتزام</span></header>
  <div class="assessment-form-banner">التقرير التفصيلي لحالات عدم الالتزام والالتزام الجزئي</div>
  <table class="assessment-form-table">
    <tr><td class="assessment-sec-head" colspan="4">أولاً: البيانات الأساسية والإطار التنظيمي</td></tr>
    <tr>
      <td class="assessment-label">اسم المشرع</td><td class="assessment-value">${v("legislator")}</td>
      <td class="assessment-label">مستوى المخاطر الكامنة</td><td class="assessment-value">${v("inherent")}</td>
    </tr>
    <tr>
      <td class="assessment-label">اسم النظام</td><td class="assessment-value">${v("system_name")}</td>
      <td class="assessment-label">حالة الالتزام</td><td class="assessment-value">${v("compliance_status")}</td>
    </tr>
    <tr>
      <td class="assessment-label">اسم الهيئة</td><td class="assessment-value">${v("authority")}</td>
      <td class="assessment-label">رقم المادة</td><td class="assessment-value">${v("article_no")}</td>
    </tr>
    <tr>
      <td class="assessment-label">اسم اللائحة</td>
      <td class="assessment-value" colspan="3">${v("regulation")}</td>
    </tr>
    <tr><td class="assessment-sec-head" colspan="4">ثانياً: نص المادة ومتطلبات الالتزام</td></tr>
    <tr><td class="assessment-label-block" colspan="4">نص المادة / المتطلب النظامي</td></tr>
    <tr><td class="assessment-value-block is-tall" colspan="4">${v("legal_text")}</td></tr>
    <tr><td class="assessment-label-block" colspan="4">البنود/المتطلبات غير الملتزم بها</td></tr>
    <tr><td class="assessment-value-block is-compact" colspan="4">${v("noncompliant_items")}</td></tr>
    <tr><td class="assessment-sec-head" colspan="4">ثالثاً: تقييم مخاطر عدم الالتزام والضوابط الرقابية</td></tr>
    <tr><td class="assessment-label-block" colspan="4">مخاطر عدم الالتزام</td></tr>
    <tr><td class="assessment-value-block is-tall" colspan="4">${v("noncompliance_risk")}</td></tr>
    <tr><td class="assessment-label-block" colspan="4">الإجراء / الخطة التصحيحية</td></tr>
    <tr><td class="assessment-value-block is-tall" colspan="4">${v("corrective_plan")}</td></tr>
    <tr><td class="assessment-sec-head" colspan="4">رابعاً: خطة التصحيح وإسناد المسؤوليات</td></tr>
    <tr>
      <td class="assessment-label">الإدارة المسؤولة عن التنفيذ</td><td class="assessment-value">${v("department")}</td>
      <td class="assessment-label">تاريخ التصحيح المستهدف</td><td class="assessment-value">${v("target_date")}</td>
    </tr>
  </table>
</article>`;
        }

        function closeAssessmentForms() {
            const modal = document.getElementById("assessmentFormsModal");
            if (modal) {
                modal.hidden = true;
                modal.style.display = "none";
            }
        }

        function renderAssessmentForms(forms) {
            assessmentGeneratedForms = Array.isArray(forms) ? forms : [];
            const mount = document.getElementById("assessmentFormsMount");
            const meta = document.getElementById("assessmentFormsMeta");
            const modal = document.getElementById("assessmentFormsModal");
            if (!mount || !modal) {
                return;
            }
            if (!assessmentGeneratedForms.length) {
                mount.innerHTML = '<p class="assessment-form-empty">لا توجد صفوف قيمتها new في عمود التقرير التفصيلي.</p>';
            } else {
                mount.innerHTML = assessmentGeneratedForms.map(assessmentFormPageHtml).join("");
            }
            if (meta) {
                meta.textContent = assessmentGeneratedForms.length
                    ? `${toEnglishNumber(assessmentGeneratedForms.length)} نموذج جاهز للطباعة والتنزيل`
                    : "لا توجد نماذج";
            }
            modal.hidden = false;
            modal.style.display = "flex";
            syncReportBrandLogos();
        }

        async function generateAssessmentForms() {
            const btn = document.getElementById("assessmentGenerateBtn");
            if (btn) {
                btn.disabled = true;
            }
            try {
                const fromRows = recordListRows.map((row) => row.form).filter(Boolean);
                if (fromRows.length) {
                    renderAssessmentForms(fromRows);
                    return;
                }
                const qs = buildFilterQueryString(state);
                qs.set("assessment_new", "1");
                const response = await fetch(`${arApiUrl("/assessment-forms")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                const data = await response.json();
                renderAssessmentForms(data.forms || []);
            } catch (_err) {
                renderAssessmentForms([]);
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        function downloadAssessmentWordHtml(forms) {
            const pages = (forms || []).map(assessmentFormPageHtml).join("");
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>نتائج تقييم خلال السنة الحالية</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; background: #fff; }
  .assessment-form-page { page-break-after: always; margin: 0 0 28px; border: 2px solid #1F4E79; }
  .assessment-form-page + .assessment-form-page { border-top: 4px solid #1F4E79; padding-top: 8px; }
  .assessment-form-brand { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; border-bottom: 1px solid #dbe3ee; }
  .assessment-form-brand img { height: 48px; max-width: 180px; object-fit: contain; }
  .assessment-form-brand-label { font-weight: 800; color: #1F4E79; font-size: 11pt; }
  .assessment-form-table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 12pt; }
  .assessment-form-table td { border: 1px solid #9aa5b1; padding: 8px 10px; vertical-align: top; }
  .assessment-sec-head { background: #2E75B6; color: #fff; font-weight: 800; text-align: center; }
  .assessment-label, .assessment-label-block { font-weight: 800; color: #1F4E79; }
  .assessment-value-block { min-height: 64px; white-space: pre-wrap; }
</style>
</head>
<body>${pages || "<p>لا توجد بيانات</p>"}</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "نتائج-تقييم-خلال-السنة-الحالية.doc";
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        async function downloadAssessmentWord() {
            const btn = document.getElementById("assessmentDownloadWordBtn");
            const forms = assessmentGeneratedForms;
            if (btn) {
                btn.disabled = true;
            }
            try {
                const isLive = Boolean((window.__AR_DASHBOARD__ || {}).isLive);
                if (isLive) {
                    const qs = buildFilterQueryString(state);
                    qs.set("assessment_new", "1");
                    const response = await fetch(`${arApiUrl("/export-assessment-forms-docx")}?${qs.toString()}`, {
                        credentials: "same-origin"
                    });
                    if (response.ok) {
                        const blob = await response.blob();
                        const a = document.createElement("a");
                        a.href = URL.createObjectURL(blob);
                        a.download = "نتائج-تقييم-خلال-السنة-الحالية.docx";
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(a.href), 1500);
                        return;
                    }
                }
                downloadAssessmentWordHtml(forms);
            } catch (_err) {
                downloadAssessmentWordHtml(forms);
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        function downloadRegisterWordHtml(rows, options) {
            const includeYears = Boolean(options && options.includeYears);
            const title = (options && options.title) || "تقرير تتبع حالة الالتزام السنوي";
            const filename = (options && options.filename) || "تقرير-تتبع-حالة-الالتزام-السنوي.doc";
            const logoSrc = currentBrandLogoSrc();
            const logoHtml = logoSrc
                ? `<img src="${escapeAssessmentHtml(logoSrc)}" alt="" style="height:52px;max-width:180px;object-fit:contain;">`
                : "";
            const colSpan = includeYears ? 7 : 5;
            const yearCells = includeYears
                ? `<th class="th-year">السنة السابقة</th><th class="th-year">السنة الحالية</th>`
                : "";
            const bodyRows = (rows || []).map((row) => {
                const obs = escapeAssessmentHtml(row.observation || "—");
                const sys = row.system_name && row.system_name !== row.observation
                    ? `<div style="color:#64748b;font-size:11px;margin-top:4px;font-weight:700;">${escapeAssessmentHtml(row.system_name)}</div>`
                    : "";
                const years = includeYears
                    ? `<td>${escapeAssessmentHtml(row.final_prev || "—")}</td>
                    <td style="font-weight:800;">${escapeAssessmentHtml(row.final_curr || "—")}</td>`
                    : "";
                return `<tr>
                    <td>${escapeAssessmentHtml(row.legislator || "—")}</td>
                    <td>${escapeAssessmentHtml(row.article_no || "—")}</td>
                    <td>${obs}${sys}</td>
                    <td>${escapeAssessmentHtml(row.rating || "—")}</td>
                    <td>${escapeAssessmentHtml(row.department || "—")}</td>
                    ${years}
                </tr>`;
            }).join("");
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>${escapeAssessmentHtml(title)}</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; color: #1e293b; }
  .brand { display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid #1F4E79; padding-bottom: 10px; margin-bottom: 14px; }
  .kicker { color: #1F4E79; font-weight: 800; margin: 0; font-size: 12pt; }
  h1 { color: #1F4E79; font-size: 20pt; margin: 8px 0 16px; }
  table { width: 100%; border-collapse: collapse; table-layout: fixed; font-size: 11pt; }
  th, td { border: 1px solid #9aa5b1; padding: 8px 10px; vertical-align: top; }
  th { font-weight: 800; text-align: center; }
  .th-leg { background: #ECFEFF; color: #155e75; }
  .th-art { background: #EEF2FF; color: #3730a3; }
  .th-obs { background: #DBEAFE; color: #1e3a8a; }
  .th-risk { background: #1F4E79; color: #fff; }
  .th-dept { background: #E2E8F0; color: #334155; }
  .th-year { background: #FEF3C7; color: #92400e; }
</style>
</head>
<body>
  <div class="brand">${logoHtml}<p class="kicker">إدارة الالتزام</p></div>
  <h1>${escapeAssessmentHtml(title)}</h1>
  <table>
    <thead>
      <tr>
        <th class="th-leg">المشرع</th>
        <th class="th-art">رقم المادة</th>
        <th class="th-obs">النص / المتطلب</th>
        <th class="th-risk">مستوى المخاطر</th>
        <th class="th-dept">الإدارة</th>
        ${yearCells}
      </tr>
    </thead>
    <tbody>${bodyRows || `<tr><td colspan="${colSpan}">لا توجد سجلات مطابقة.</td></tr>`}</tbody>
  </table>
</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        function registerWordFallback() {
            if (recordListShowAssessmentNew) {
                downloadRegisterWordHtml(recordListRows, {
                    includeYears: false,
                    title: "نتائج تقييم خلال السنة الحالية",
                    filename: "نتائج-تقييم-خلال-السنة-الحالية.doc",
                });
                return;
            }
            downloadRegisterWordHtml(recordListRows, {
                includeYears: true,
                title: "تقرير تتبع حالة الالتزام السنوي",
                filename: "تقرير-تتبع-حالة-الالتزام-السنوي.doc",
            });
        }

        async function downloadRecordListWord() {
            const btn = document.getElementById("annualTrackingWordBtn");
            if (btn) {
                btn.disabled = true;
            }
            try {
                const isLive = Boolean((window.__AR_DASHBOARD__ || {}).isLive);
                if (isLive) {
                    const qs = buildFilterQueryString(state);
                    const isAssessment = recordListShowAssessmentNew;
                    if (isAssessment) {
                        qs.set("assessment_new", "1");
                    } else {
                        qs.set("final_status_change", "1");
                    }
                    const path = isAssessment ? "/export-assessment-list-docx" : "/export-annual-tracking-docx";
                    const response = await fetch(`${arApiUrl(path)}?${qs.toString()}`, {
                        credentials: "same-origin"
                    });
                    if (response.ok) {
                        const blob = await response.blob();
                        const a = document.createElement("a");
                        a.href = URL.createObjectURL(blob);
                        a.download = isAssessment
                            ? "نتائج-تقييم-خلال-السنة-الحالية.docx"
                            : "تقرير-تتبع-حالة-الالتزام-السنوي.docx";
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(a.href), 1500);
                        return;
                    }
                }
                registerWordFallback();
            } catch (_err) {
                registerWordFallback();
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        function handleDimensionClick(stateKey, value, displayLabel) {
            const arr = state[stateKey];
            if (!Array.isArray(arr)) {
                return;
            }
            const drillKey = `${stateKey}:${value}`;
            const already = arr.includes(value);
            if (!already) {
                arr.push(value);
                lastTileDrillKey = "";
                closeRecordList();
                fetchSummary();
                return;
            }
            if (isRecordListOpen() && lastTileDrillKey === drillKey) {
                closeRecordList();
                lastTileDrillKey = "";
                arr.splice(arr.indexOf(value), 1);
                fetchSummary();
                return;
            }
            lastTileDrillKey = drillKey;
            const label = displayLabel || value;
            const isQuarterLabel = /^Q[1-4]$/i.test(String(label || "").trim());
            const showQuarters = stateKey === "actual_annual" || stateKey === "target_annual";
            openRecordList(showQuarters ? label : (isQuarterLabel ? "السجلات" : label), {
                skip_quarters: !showQuarters,
                year_compliance: stateKey === "year"
            });
        }

        const groupMeta = {
            control_category: {
                apiKey: "فئة الضوابط الرقابية",
                elementId: "row-control-category",
                totalColor: "#111111",
                colors: ["#166534", "#15803d", "#16a34a", "#22c55e", "#4ade80", "#86efac", "#bbf7d0"]
            },
            inherent: {
                apiKey: "مستوى المخاطر الكامنة",
                elementId: "row-residual",
                totalColor: "#111111",
                colors: ["#3d7a5a", "#c9a227", "#c24141", "#8f1d2c", "#5a8f6e", "#7b8794"]
            },
            status: {
                apiKey: "حالة الخطة التصحيحية",
                elementId: "row-status",
                totalColor: "#111111",
                colors: ["#3d7a5a", "#5a8f6e", "#c9a227", "#c24141", "#8f1d2c", "#7b8794"]
            },
            year: {
                apiKey: "تاريخ خطة الالتزام",
                elementId: "row-year",
                totalColor: "#111111",
                colors: ["#3730a3", "#4338ca", "#4f46e5", "#6366f1", "#818cf8", "#a5b4fc", "#c7d2fe"]
            },
            assessment_year: {
                apiKey: "نتائج التقييم خلال السنة الحالية",
                elementId: "row-assessment-year",
                totalColor: "#111111",
                colors: ["#0e7490", "#0891b2", "#06b6d4", "#22d3ee", "#67e8f9", "#a5f3fc"]
            },
            target_annual: {
                apiKey: "تاريخ التصحيح السنوي المستهدف",
                elementId: "row-target-annual",
                totalColor: "#111111",
                colors: ["#1d4ed8", "#2563eb", "#3b82f6", "#60a5fa", "#93c5fd", "#bfdbfe"]
            },
            actual_annual: {
                apiKey: "تاريخ التصحيح السنوي الفعلي",
                elementId: "row-actual-annual",
                totalColor: "#111111",
                colors: ["#4b5563", "#6b7280", "#7b8594", "#8b95a3", "#9aa3b0", "#a8b0bb"]
            },
        };
        const SUBSIDIARY_API_KEY = "الشركة التابعة";
        const HOLDING_API_KEY = "الشركة القابضة";
        const SUBSIDIARY_BRAND_ORDER = ["nat", "aum", "saco", "autostar", "btc"];
        let companyBrandMode = "subsidiary";
        let subsidiaryListBound = false;

        function companyBrandApiKey() {
            return companyBrandMode === "holding" ? HOLDING_API_KEY : SUBSIDIARY_API_KEY;
        }

        function companyBrandStateKey() {
            return companyBrandMode === "holding" ? "holding_company" : "subsidiary_company";
        }

        function resolveCompanyBrandMode(flags) {
            if (flags && flags.subsidiary) {
                return "subsidiary";
            }
            if (flags && flags.holding) {
                return "holding";
            }
            return "";
        }
        const fieldMeta = {
            department: { apiKey: "الإدارة المسؤولة", label: "الإدارة المسؤولة", color: "#c24141" },
            legislator: { apiKey: "المشرع", label: "المشرع", color: "#1e3a5f" },
            system_name: { apiKey: "اسم النظام", label: "النظام", color: "#0f766e" },
            regulation: { apiKey: "اللائحة", label: "اللائحة", color: "#64748b" },
            authority: { apiKey: "الهيئة التابعة", label: "الهيئة التابعة", color: "#b45309" }
        };
        const standaloneSelectMeta = {
            legal_text: { apiKey: "النص النظامي", elementId: "legalTextFilter" }
        };
        const charts = {};
        let summaryFetchController = null;
        let legalDetailsController = null;
        const chartToStateKey = {
            statusChart: "status",
            complianceStatusChart: "compliance_status",
            residualChart: "inherent",
            controlCategoryChart: "control_category"
        };

        function toEnglishNumber(value) {
            return Number(value).toLocaleString("en-US");
        }

        function escapeHtml(value) {
            return String(value)
                .replaceAll("&", "&amp;")
                .replaceAll("<", "&lt;")
                .replaceAll(">", "&gt;")
                .replaceAll('"', "&quot;")
                .replaceAll("'", "&#039;");
        }

        function colorFor(groupName, index) {
            const palette = groupMeta[groupName].colors;
            return palette[index % palette.length];
        }

        function tileTextColor(hex) {
            const h = String(hex || "").replace("#", "");
            if (h.length !== 6) {
                return "#ffffff";
            }
            const r = parseInt(h.slice(0, 2), 16);
            const g = parseInt(h.slice(2, 4), 16);
            const b = parseInt(h.slice(4, 6), 16);
            const luma = (r * 299 + g * 587 + b * 114) / 1000;
            return luma > 165 ? "#0f172a" : "#ffffff";
        }

        function stripArabicTashkeel(s) {
            return String(s || "")
                .normalize("NFKC")
                .replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g, "");
        }

        function statusColorByLabel(label, fallbackColor) {
            const text = stripArabicTashkeel(String(label || "").trim()).replace(/\s+/g, " ");
            if (text.includes("مغلق") || text.includes("مقفل") || text.includes("مغلف")) {
                return "#3d7a5a";
            }
            if (text.includes("مفتوح") && text.includes("تجاوز تاريخ التصحيح")) {
                return "#c24141";
            }
            if (text.includes("مفتوح") && text.includes("ضمن تاريخ التصحيح")) {
                return "#c9a227";
            }
            if (text.includes("تجاوز")) {
                return "#c24141";
            }
            if (text.includes("ضمن")) {
                return "#c9a227";
            }
            return fallbackColor;
        }

        const BLANK_TOKEN = "(blank)";

        function withoutBlankItems(items) {
            return (items || []).filter((item) => {
                if (!item) {
                    return false;
                }
                const key = String(item.key ?? "").trim();
                const label = String(item.label ?? "").trim();
                return key !== BLANK_TOKEN && label !== BLANK_TOKEN && key.toLowerCase() !== "blank";
            });
        }

        function sumDimensionCounts(items) {
            return (items || []).reduce((sum, item) => sum + Number(item && item.count ? item.count : 0), 0);
        }

        /** RTL: أول عنصر = أقصى اليمين — أخضر ثم أصفر ثم أحمر (الأحمر يسار) */
        function complianceStatusSortRank(label) {
            const t = stripArabicTashkeel(String(label || "").trim()).normalize("NFKC");
            const compact = t.replace(/\s/g, "");
            if (t === BLANK_TOKEN) {
                return 9000;
            }
            if (compact.includes("غيرملتزم") || /غير\s+ملتزم/.test(t)) {
                return 30;
            }
            if (t.includes("ملتزم جزئي") || t === "جزئي" || t.includes("جزئي")) {
                return 20;
            }
            if (t.includes("ملتزم")) {
                return 10;
            }
            return 200 + [...t].reduce((s, ch) => s + ch.charCodeAt(0), 0) % 500;
        }

        function sortComplianceItems(items) {
            return [...items].sort(
                (a, b) =>
                    complianceStatusSortRank(a.key) - complianceStatusSortRank(b.key) ||
                    String(a.key).localeCompare(String(b.key), "ar")
            );
        }

        function correctiveStatusSortRank(label) {
            const t = stripArabicTashkeel(String(label || "").trim()).normalize("NFKC");
            if (t === BLANK_TOKEN) {
                return 9000;
            }
            if (t.includes("تجاوز")) {
                return 10;
            }
            if (t.includes("ضمن")) {
                return 20;
            }
            if (t.includes("مغلق") || t.includes("مقفل") || t.includes("مغلف")) {
                return 30;
            }
            return 200 + [...t].reduce((s, ch) => s + ch.charCodeAt(0), 0) % 500;
        }

        function sortCorrectiveStatusItems(items) {
            return [...items].sort(
                (a, b) =>
                    correctiveStatusSortRank(a.key) - correctiveStatusSortRank(b.key) ||
                    String(a.key).localeCompare(String(b.key), "ar")
            );
        }

        /** ترتيب شريط «مستوى المخاطر الكامنة» في RTL: أول عنصر = أقصى اليمين — منخفض (أخضر) ثم متوسط ثم مرتفع ثم مرتفع جداً */
        function residualRiskSortRank(label) {
            const raw = String(label ?? "").trim();
            if (raw === BLANK_TOKEN) {
                return 8000;
            }
            const t = stripArabicTashkeel(raw).normalize("NFKC").replace(/\s+/g, " ");
            if (t.includes("متدني") && /انخفاض|انخفاظ|انخغاض|انخفاق/.test(t)) {
                return 5;
            }
            if (t.includes("منخفض") && !t.includes("متدني")) {
                return 15;
            }
            if (t.includes("متوسط")) {
                return 25;
            }
            if ((t.includes("جدا") || t.includes("جداً") || t.includes("جدآ")) && (t.includes("مرتفع") || t.includes("مرفع") || t.includes("مرتفغ") || t.includes("مرنفع"))) {
                return 45;
            }
            if (t.includes("مرتفع") || t.includes("مرفع") || t.includes("مرتفغ") || t.includes("مرنفع")) {
                return 35;
            }
            return 200 + [...t].reduce((s, ch) => s + ch.charCodeAt(0), 0) % 500;
        }

        function sortResidualItems(items) {
            return [...items].sort(
                (a, b) =>
                    residualRiskSortRank(a.key) - residualRiskSortRank(b.key) ||
                    String(a.key).localeCompare(String(b.key), "ar")
            );
        }

        function inherentRiskItems(items) {
            return sortResidualItems(withoutBlankItems(items));
        }

        /** ألوان ثابتة: منخفض أخضر، متوسط أصفر، مرتفع أحمر، مرتفع جداً أحمر داكن */
        function residualRiskSegmentStyle(label) {
            const raw = String(label ?? "").trim();
            if (raw === BLANK_TOKEN) {
                return { background: "#7b8794", color: "#ffffff" };
            }
            const t = stripArabicTashkeel(raw).normalize("NFKC").replace(/\s+/g, " ");
            if (t.includes("متدني") && /انخفاض|انخفاظ|انخغاض|انخفاق/.test(t)) {
                return { background: "#5a8f6e", color: "#ffffff" };
            }
            if ((t.includes("جدا") || t.includes("جداً") || t.includes("جدآ")) && (t.includes("مرتفع") || t.includes("مرفع") || t.includes("مرتفغ") || t.includes("مرنفع"))) {
                return { background: "#8f1d2c", color: "#ffffff" };
            }
            if (t.includes("مرتفع") || t.includes("مرفع") || t.includes("مرتفغ") || t.includes("مرنفع")) {
                return { background: "#c24141", color: "#ffffff" };
            }
            if (t.includes("متوسط")) {
                return { background: "#c9a227", color: "#1e293b" };
            }
            if (t.includes("منخفض") && !t.includes("متدني")) {
                return { background: "#3d7a5a", color: "#ffffff" };
            }
            return { background: "#7b8794", color: "#ffffff" };
        }

        function complianceSegmentStyle(label, isTotal) {
            if (isTotal) {
                return { background: "#0f2744", color: "#ffffff" };
            }
            const t = stripArabicTashkeel(String(label || "").trim()).normalize("NFKC");
            const compact = t.replace(/\s/g, "");
            if (t === BLANK_TOKEN) {
                return { background: "#7b8794", color: "#ffffff" };
            }
            if (compact.includes("غيرملتزم") || /غير\s+ملتزم/.test(t)) {
                return { background: "#c24141", color: "#ffffff" };
            }
            if (t.includes("متدني") && /انخفاض|انخفاظ|انخفاق|انخغاض/.test(t)) {
                return { background: "#5a8f6e", color: "#ffffff" };
            }
            if ((t.includes("جدا") || t.includes("جداً") || t.includes("جدآ")) && (t.includes("مرتفع") || t.includes("مرفع"))) {
                return { background: "#8f1d2c", color: "#ffffff" };
            }
            if (t.includes("مرتفع") || t.includes("مرفع")) {
                return { background: "#c24141", color: "#ffffff" };
            }
            if (t.includes("متوسط")) {
                return { background: "#c9a227", color: "#1e293b" };
            }
            if (t.includes("منخفض") && !t.includes("متدني")) {
                return { background: "#3d7a5a", color: "#ffffff" };
            }
            if (t.includes("ملتزم جزئي")) {
                return { background: "#c9a227", color: "#1e293b" };
            }
            if (t === "جزئي" || t.includes("جزئي")) {
                return { background: "#c24141", color: "#ffffff" };
            }
            if (t.includes("ملتزم")) {
                return { background: "#3d7a5a", color: "#ffffff" };
            }
            return { background: "#7b8794", color: "#ffffff" };
        }

        function renderComplianceStatusRow(data) {
            const apiKey = "حالة الالتزام بالمتطلبات";
            const wrap = document.getElementById("complianceSegBar");
            if (!wrap) {
                return;
            }
            const raw = data.groups[apiKey] || [];
            const sorted = sortComplianceItems(withoutBlankItems(raw));
            wrap.innerHTML = "";

            sorted.forEach((item) => {
                const seg = document.createElement("button");
                seg.type = "button";
                seg.className = "tile";
                if (state.compliance_status.includes(item.key)) {
                    seg.classList.add("selected");
                }
                const vis = complianceSegmentStyle(item.label, false);
                seg.style.background = vis.background;
                seg.style.color = vis.color;
                seg.innerHTML = `<div class="tile-number">${toEnglishNumber(item.count)}</div><div class="tile-label">${escapeHtml(
                    item.label
                )}</div>`;
                seg.title = `انقر للفلترة، ثم مرة أخرى لعرض السجلات: ${item.label}`;
                seg.addEventListener("click", () => {
                    handleDimensionClick("compliance_status", item.key, item.label);
                });
                wrap.appendChild(seg);
            });

            const totalSeg = document.createElement("button");
            totalSeg.type = "button";
            totalSeg.className = "tile tile-total";
            totalSeg.title = "مسح فلتر حالة الالتزام بالمتطلبات";
            totalSeg.innerHTML = `<div class="tile-number">${toEnglishNumber(
                sumDimensionCounts(sorted)
            )}</div><div class="tile-label">Total</div>`;
            totalSeg.addEventListener("click", () => {
                clearRowFilter("compliance_status");
            });
            wrap.appendChild(totalSeg);
        }

        function appendTotalTile(track, groupName, items) {
            const totalTile = document.createElement("button");
            totalTile.type = "button";
            totalTile.className = "tile tile-total";
            const totalValue = document.createElement("div");
            totalValue.className = "tile-number";
            totalValue.textContent = toEnglishNumber(sumDimensionCounts(items));
            const totalLabel = document.createElement("div");
            totalLabel.className = "tile-label";
            totalLabel.textContent = "Total";
            totalTile.appendChild(totalValue);
            totalTile.appendChild(totalLabel);
            totalTile.style.background = groupMeta[groupName].totalColor || "#111111";
            totalTile.style.color = "#ffffff";
            totalTile.title = "مسح فلتر هذا الصف";
            totalTile.addEventListener("click", () => {
                clearRowFilter(groupName);
            });
            track.appendChild(totalTile);
        }

        function buildTile(groupName, item, index, totalCount) {
            const tile = document.createElement("button");
            tile.type = "button";
            tile.className = "tile";
            let baseColor = colorFor(groupName, index);
            if (groupName === "inherent") {
                const vis = residualRiskSegmentStyle(item.label);
                tile.style.background = vis.background;
                tile.style.color = vis.color;
            } else if (groupName === "status") {
                const bg = statusColorByLabel(item.label, baseColor);
                tile.style.background = bg;
                tile.style.color = bg === "#c9a227" ? "#1e293b" : "#ffffff";
            } else {
                tile.style.background = baseColor;
                tile.style.color = tileTextColor(baseColor);
            }
            tile.dataset.value = item.key;
            tile.dataset.group = groupName;

            if (state[groupName].includes(item.key)) {
                tile.classList.add("selected");
            }

            const value = document.createElement("div");
            value.className = "tile-number";
            value.textContent = toEnglishNumber(item.count);

            const label = document.createElement("div");
            label.className = "tile-label";
            label.textContent = item.label;

            tile.appendChild(value);
            tile.appendChild(label);
            tile.title = `انقر للفلترة، ثم مرة أخرى لعرض السجلات: ${item.label}`;
            tile.addEventListener("click", () => {
                handleDimensionClick(groupName, item.key, item.label);
            });

            const track = document.getElementById(groupMeta[groupName].elementId);
            track.appendChild(tile);
        }

        function clearRowFilter(stateKey) {
            if (!Array.isArray(state[stateKey])) {
                return;
            }
            state[stateKey].length = 0;
            if (String(lastTileDrillKey).startsWith(`${stateKey}:`)) {
                lastTileDrillKey = "";
                closeRecordList();
            }
            fetchSummary();
        }

        function pruneStaleFilters(data) {
            const groups = data.groups || {};
            const prune = (stateKey, apiKey) => {
                if (!Array.isArray(state[stateKey])) {
                    return;
                }
                if (!(apiKey in groups)) {
                    state[stateKey].length = 0;
                    return;
                }
                const valid = new Set((groups[apiKey] || []).map((item) => item.key));
                state[stateKey] = state[stateKey].filter((v) => valid.has(v));
            };
            Object.entries(groupMeta).forEach(([stateKey, meta]) => prune(stateKey, meta.apiKey));
            Object.entries(fieldMeta).forEach(([stateKey, meta]) => prune(stateKey, meta.apiKey));
            prune("subsidiary_company", SUBSIDIARY_API_KEY);
            prune("holding_company", HOLDING_API_KEY);
            prune("compliance_status", "حالة الالتزام بالمتطلبات");
            prune("legal_text", "النص النظامي");
        }

        function subsidiaryDisplayLabel(key) {
            const code = String(key || "").trim();
            if (BRAND_LOGO_CODES.has(code)) {
                return code.toUpperCase();
            }
            return code;
        }

        function sortSubsidiaryItems(items) {
            const rank = (key) => {
                const k = String(key).trim().toLowerCase();
                const idx = SUBSIDIARY_BRAND_ORDER.indexOf(k);
                return idx >= 0 ? idx : 100 + [...String(key)].reduce((s, ch) => s + ch.charCodeAt(0), 0);
            };
            return withoutBlankItems(items)
                .sort((a, b) => rank(a.key) - rank(b.key) || String(a.key).localeCompare(String(b.key), "ar"));
        }

        function syncSubsidiaryListSelection() {
            const list = document.getElementById("subsidiaryList");
            if (!list) {
                return;
            }
            const selected = new Set(state[companyBrandStateKey()]);
            list.querySelectorAll(".subsidiary-list-item").forEach((btn) => {
                const on = selected.has(btn.dataset.value);
                btn.classList.toggle("selected", on);
                btn.setAttribute("aria-selected", on ? "true" : "false");
            });
        }

        function readSubsidiaryListSelection() {
            const list = document.getElementById("subsidiaryList");
            if (!list) {
                return;
            }
            state[companyBrandStateKey()] = Array.from(list.querySelectorAll(".subsidiary-list-item.selected")).map(
                (btn) => btn.dataset.value
            );
        }

        function updateSubsidiaryStatusPill() {
            const pill = document.getElementById("subsidiaryStatusPill");
            if (!pill) {
                return;
            }
            const selected = state[companyBrandStateKey()];
            const allLabel =
                companyBrandMode === "holding"
                    ? "جميع الشركات القابضة (الفلتر اختياري — غير مفعّل)"
                    : "جميع الشركات التابعة (الفلتر اختياري — غير مفعّل)";
            if (!selected.length) {
                pill.textContent = allLabel;
                pill.classList.remove("active");
                return;
            }
            const labels = selected.map(subsidiaryDisplayLabel).join(", ");
            pill.textContent = `مفعّل: ${labels}`;
            pill.classList.add("active");
        }

        function applySubsidiaryFilterFromList() {
            readSubsidiaryListSelection();
            updateSubsidiaryStatusPill();
            fetchSummary();
        }

        function bindSubsidiaryListOnce() {
            if (subsidiaryListBound) {
                return;
            }
            const list = document.getElementById("subsidiaryList");
            const selectAllBtn = document.getElementById("subsidiarySelectAllBtn");
            const deselectAllBtn = document.getElementById("subsidiaryDeselectAllBtn");
            const changeBtn = document.getElementById("subsidiaryChangeBtn");
            if (!list) {
                return;
            }
            subsidiaryListBound = true;
            list.addEventListener("click", (event) => {
                const item = event.target.closest(".subsidiary-list-item");
                if (!item) {
                    return;
                }
                item.classList.toggle("selected");
                applySubsidiaryFilterFromList();
            });
            if (selectAllBtn) {
                selectAllBtn.addEventListener("click", () => {
                    list.querySelectorAll(".subsidiary-list-item").forEach((btn) => {
                        btn.classList.add("selected");
                    });
                    applySubsidiaryFilterFromList();
                });
            }
            if (deselectAllBtn) {
                deselectAllBtn.addEventListener("click", () => {
                    list.querySelectorAll(".subsidiary-list-item").forEach((btn) => {
                        btn.classList.remove("selected");
                    });
                    applySubsidiaryFilterFromList();
                });
            }
            if (changeBtn) {
                changeBtn.addEventListener("click", () => {
                    list.focus();
                });
            }
        }

        function renderSubsidiaryCompanyPanel(data) {
            const section = document.getElementById("subsidiary-company-section");
            const pageTop = section && section.closest(".page-top");
            const list = document.getElementById("subsidiaryList");
            const titleEl = document.getElementById("companyBrandTitle");
            const subtitleEl = document.getElementById("companyBrandSubtitle");
            if (!section || !list) {
                return;
            }
            const flags = data.company_columns || {};
            companyBrandMode = resolveCompanyBrandMode(flags);
            const visible = Boolean(companyBrandMode);
            section.hidden = !visible;
            if (pageTop) {
                pageTop.hidden = !visible;
            }
            if (!visible) {
                return;
            }
            if (titleEl) {
                titleEl.textContent = companyBrandMode === "holding" ? "الشركة القابضة" : "الشركة التابعة";
            }
            if (subtitleEl) {
                subtitleEl.textContent = companyBrandMode === "holding" ? "HOLDING" : "SUBCOMPANY";
            }
            list.setAttribute("aria-label", titleEl ? titleEl.textContent : "شركة");
            bindSubsidiaryListOnce();
            const apiKey = companyBrandApiKey();
            const items = sortSubsidiaryItems((data.groups && data.groups[apiKey]) || []);
            const previous = new Set(state[companyBrandStateKey()]);
            list.innerHTML = "";
            if (!items.length) {
                const emptyMsg =
                    companyBrandMode === "holding"
                        ? "لا توجد شركات قابضة في البيانات الحالية"
                        : "لا توجد شركات تابعة في البيانات الحالية";
                list.innerHTML = `<div class="subsidiary-list-empty">${emptyMsg}</div>`;
            } else {
                items.forEach((item) => {
                    const btn = document.createElement("button");
                    btn.type = "button";
                    btn.className = `subsidiary-list-item${previous.has(item.key) ? " selected" : ""}`;
                    btn.dataset.value = item.key;
                    btn.textContent = subsidiaryDisplayLabel(item.key);
                    btn.setAttribute("role", "option");
                    btn.setAttribute("aria-selected", previous.has(item.key) ? "true" : "false");
                    list.appendChild(btn);
                });
            }
            syncSubsidiaryListSelection();
            updateSubsidiaryStatusPill();
        }

        function renderFilterGroups(data) {
            Object.keys(groupMeta).forEach((groupName) => {
                const meta = groupMeta[groupName];
                renderGroup(groupName, (data.groups && data.groups[meta.apiKey]) || []);
            });
        }

        function renderGroup(groupName, items) {
            const track = document.getElementById(groupMeta[groupName].elementId);
            if (!track) {
                return;
            }
            track.innerHTML = "";
            const list =
                groupName === "inherent"
                    ? inherentRiskItems(items)
                    : groupName === "status"
                      ? sortCorrectiveStatusItems(withoutBlankItems(items))
                      : withoutBlankItems(items);
            if (groupName === "status") {
                appendTotalTile(track, groupName, list);
            }
            list.forEach((item, index) => buildTile(groupName, item, index, list.length));
            if (groupName !== "status" && list.length) {
                appendTotalTile(track, groupName, list);
            }
        }

        function renderFieldBoxes(data) {
            const wrap = document.getElementById("fieldBoxes");
            wrap.innerHTML = "";

            Object.keys(fieldMeta).forEach((stateKey) => {
                const apiKey = fieldMeta[stateKey].apiKey;
                if (!(apiKey in data.groups)) {
                    return;
                }
                const groupItems = withoutBlankItems(data.groups[apiKey] || []);
                const total = groupItems.length;

                const box = document.createElement("button");
                box.type = "button";
                box.className = `field-box${activeFieldKey === stateKey ? " active" : ""}`;
                box.style.background = fieldMeta[stateKey].color || "#1e3a5f";
                box.style.color = "#ffffff";
                box.innerHTML = `
                    <div class="field-box-number">${toEnglishNumber(total)}</div>
                    <div class="field-box-label">${fieldMeta[stateKey].label}</div>
                `;
                box.addEventListener("click", () => {
                    activeFieldKey = activeFieldKey === stateKey ? "" : stateKey;
                    renderFieldOptions(data);
                    renderFieldBoxes(data);
                });
                wrap.appendChild(box);
            });
        }

        function renderFieldOptions(data) {
            const panel = document.getElementById("fieldOptions");
            if (!activeFieldKey) {
                panel.style.display = "none";
                panel.innerHTML = "";
                return;
            }

            const meta = fieldMeta[activeFieldKey];
            const items = withoutBlankItems(data.groups[meta.apiKey] || []);
            panel.style.display = "block";
            panel.innerHTML = `
                <h3 class="field-options-title">اختيار من: ${meta.label}</h3>
                <ul id="optionList" class="option-list"></ul>
            `;

            const list = panel.querySelector("#optionList");
            const allItem = document.createElement("li");
            allItem.className = "option-item";
            const allBtn = document.createElement("button");
            allBtn.type = "button";
            allBtn.className = `option-btn${state[activeFieldKey].length === 0 ? " selected" : ""}`;
            allBtn.innerHTML = `<span>الكل</span>`;
            allBtn.addEventListener("click", () => {
                state[activeFieldKey].length = 0;
                fetchSummary();
            });
            allItem.appendChild(allBtn);
            list.appendChild(allItem);

            items.forEach((item) => {
                const li = document.createElement("li");
                li.className = "option-item";
                const btn = document.createElement("button");
                btn.type = "button";
                btn.className = `option-btn${state[activeFieldKey].includes(item.key) ? " selected" : ""}`;
                btn.innerHTML = `
                    <span>${item.label}</span>
                    <span class="option-count">${toEnglishNumber(item.count)}</span>
                `;
                btn.addEventListener("click", () => {
                    handleDimensionClick(activeFieldKey, item.key, item.label);
                });
                li.appendChild(btn);
                list.appendChild(li);
            });
        }

        function createInsideChartLabelsPlugin(total) {
            return {
                id: "insideChartLabels",
                afterDatasetsDraw(chart) {
                    const chartType = chart.config.type;
                    const dataset = chart.data.datasets[0];
                    const meta = chart.getDatasetMeta(0);
                    if (!dataset || !meta || !meta.data.length) {
                        return;
                    }
                    const { ctx } = chart;

                    if (chartType === "doughnut" || chartType === "pie") {
                        meta.data.forEach((arc, index) => {
                            const value = Number(dataset.data[index] || 0);
                            if (value <= 0) {
                                return;
                            }
                            const pct = total ? ((value / total) * 100).toFixed(1) : "0.0";
                            const props = arc.getProps(
                                ["x", "y", "startAngle", "endAngle", "innerRadius", "outerRadius"],
                                true
                            );
                            const angle = (props.startAngle + props.endAngle) / 2;
                            const radius = (props.innerRadius + props.outerRadius) / 2;
                            const labelX = props.x + Math.cos(angle) * radius;
                            const labelY = props.y + Math.sin(angle) * radius;
                            ctx.save();
                            ctx.fillStyle = "#0b1d38";
                            ctx.font = "700 15px sans-serif";
                            ctx.textAlign = "center";
                            ctx.textBaseline = "middle";
                            ctx.fillText(`${pct}%`, labelX, labelY);
                            ctx.restore();
                        });
                        return;
                    }

                    if (chartType === "bar") {
                        meta.data.forEach((bar, index) => {
                            const value = Number(dataset.data[index] || 0);
                            if (value <= 0) {
                                return;
                            }
                            const pct = total ? ((value / total) * 100).toFixed(1) : "0.0";
                            const props = bar.getProps(["x", "y", "base"], true);
                            const top = Math.min(props.y, props.base);
                            const bottom = Math.max(props.y, props.base);
                            const centerX = props.x;
                            const centerY = top + (bottom - top) / 2;
                            ctx.save();
                            ctx.fillStyle = "#0b1d38";
                            ctx.font = "700 15px sans-serif";
                            ctx.textAlign = "center";
                            ctx.textBaseline = "middle";
                            ctx.fillText(`${pct}%`, centerX, centerY);
                            ctx.restore();
                        });
                    }
                }
            };
        }

        function buildChartConfig(type, labels, values, colors, stateKey) {
            const total = values.reduce((sum, v) => sum + Number(v || 0), 0);
            const isArc = type === "doughnut" || type === "pie";
            const isBar = type === "bar";
            const useInsideLabels = isArc || isBar;
            const config = {
                type,
                data: {
                    labels,
                    datasets: [{ data: values, backgroundColor: colors, borderWidth: 1 }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    animation: false,
                    layout: {
                        padding: isBar
                            ? { top: 8, right: 6, bottom: 2, left: 4 }
                            : { top: 2, right: 2, bottom: 2, left: 2 }
                    },
                    onClick: (_event, elements) => {
                        if (!elements.length) {
                            return;
                        }
                        const idx = elements[0].index;
                        const clickedLabel = labels[idx];
                        handleDimensionClick(stateKey, clickedLabel, clickedLabel);
                    },
                    plugins: {
                        legend: { display: false },
                        datalabels: useInsideLabels
                            ? { display: false }
                            : {
                                  color: "#0b1d38",
                                  font: { weight: "700", size: 14 },
                                  formatter: (value) => {
                                      if (!total) {
                                          return "0%";
                                      }
                                      const pct = (Number(value) / total) * 100;
                                      return `${pct.toFixed(1)}%`;
                                  },
                                  display: (ctx) => Number(ctx.dataset.data[ctx.dataIndex] || 0) > 0
                              }
                    }
                }
            };
            if (isBar) {
                config.options.scales = {
                    x: {
                        ticks: { font: { size: 13, weight: "700" }, color: "#1e293b" }
                    },
                    y: {
                        beginAtZero: true,
                        ticks: { font: { size: 13, weight: "600" }, color: "#1e293b" }
                    }
                };
            }
            if (useInsideLabels) {
                config.plugins = [createInsideChartLabelsPlugin(total)];
            }
            return config;
        }

        function syncChartHtmlLegend(canvas, config) {
            const card = canvas.closest(".chart-card");
            if (!card) {
                return;
            }
            let legend = card.querySelector(".chart-legend");
            if (!legend) {
                legend = document.createElement("ul");
                legend.className = "chart-legend";
                canvas.parentElement.insertAdjacentElement("afterend", legend);
            }
            if (config.type === "bar") {
                legend.hidden = true;
                legend.innerHTML = "";
                return;
            }
            const labels = config.data.labels || [];
            const colors = (config.data.datasets[0] && config.data.datasets[0].backgroundColor) || [];
            legend.hidden = false;
            legend.innerHTML = labels
                .map((label, i) => {
                    const color = colors[i] || "#94a3b8";
                    return `<li><span class="chart-legend-swatch" style="background:${color}"></span><span>${escapeAssessmentHtml(label)}</span></li>`;
                })
                .join("");
        }

        function renderOrUpdateChart(id, config) {
            if (!hasChartLib) {
                return;
            }
            const canvas = document.getElementById(id);
            if (!canvas) {
                return;
            }
            if (charts[id]) {
                charts[id].destroy();
                delete charts[id];
            }
            charts[id] = new Chart(canvas, config);
            syncChartHtmlLegend(canvas, config);
        }

        function updateTopCharts(data) {
            const statusItems = sortCorrectiveStatusItems(
                withoutBlankItems(data.groups[groupMeta.status.apiKey] || [])
            );
            const residualItems = inherentRiskItems(data.groups[groupMeta.inherent.apiKey] || []);
            const controlItems = withoutBlankItems(data.groups[groupMeta.control_category.apiKey] || []);
            const complianceItems = sortComplianceItems(
                withoutBlankItems(data.groups["حالة الالتزام بالمتطلبات"] || [])
            );

            renderOrUpdateChart(
                "statusChart",
                buildChartConfig(
                    "doughnut",
                    statusItems.map((x) => x.label),
                    statusItems.map((x) => x.count),
                    statusItems.map((x, i) => statusColorByLabel(x.label, colorFor("status", i))),
                    chartToStateKey.statusChart
                )
            );

            renderOrUpdateChart(
                "complianceStatusChart",
                buildChartConfig(
                    "pie",
                    complianceItems.map((x) => x.label),
                    complianceItems.map((x) => x.count),
                    complianceItems.map((x) => complianceSegmentStyle(x.label, false).background),
                    chartToStateKey.complianceStatusChart
                )
            );

            renderOrUpdateChart(
                "residualChart",
                buildChartConfig(
                    "doughnut",
                    residualItems.map((x) => x.label),
                    residualItems.map((x) => x.count),
                    residualItems.map((x) => residualRiskSegmentStyle(x.label).background),
                    chartToStateKey.residualChart
                )
            );

            renderOrUpdateChart(
                "controlCategoryChart",
                buildChartConfig(
                    "bar",
                    controlItems.map((x) => x.label),
                    controlItems.map((x) => x.count),
                    controlItems.map((_, i) => colorFor("control_category", i)),
                    chartToStateKey.controlCategoryChart
                )
            );
        }

        const compliancePlanModal = document.getElementById("compliancePlanModal");
        const compliancePlanEditor = document.getElementById("compliancePlanEditor");
        const compliancePlanFileInput = document.getElementById("compliancePlanFileInput");
        const compliancePlanSheetSelect = document.getElementById("compliancePlanSheetSelect");
        const compliancePlanColorInput = document.getElementById("compliancePlanColor");
        let complianceWorkbook = null;
        const compliancePlanState = {
            sheetName: "",
            headers: [],
            rows: [],
            styles: {},
            selectedCell: null
        };

        function restoreCompliancePlanState() {
            try {
                const embedded = document.getElementById("compliance-plan-seed");
                if (!embedded || !embedded.textContent) {
                    return;
                }
                const parsed = JSON.parse(embedded.textContent);
                if (!parsed || typeof parsed !== "object") return;
                compliancePlanState.sheetName = String(parsed.sheetName || "");
                compliancePlanState.headers = Array.isArray(parsed.headers) ? parsed.headers.map((x) => String(x ?? "")) : [];
                compliancePlanState.rows = Array.isArray(parsed.rows)
                    ? parsed.rows.map((r) => (Array.isArray(r) ? r.map((x) => String(x ?? "")) : []))
                    : [];
                compliancePlanState.styles = parsed.styles && typeof parsed.styles === "object" ? parsed.styles : {};
                compliancePlanState.selectedCell = parsed.selectedCell ? String(parsed.selectedCell) : null;
                compliancePlanSheetSelect.innerHTML = "";
                if (compliancePlanState.sheetName) {
                    const opt = document.createElement("option");
                    opt.value = compliancePlanState.sheetName;
                    opt.textContent = `${compliancePlanState.sheetName} (محفوظ)`;
                    opt.selected = true;
                    compliancePlanSheetSelect.appendChild(opt);
                }
            } catch (_e) {}
        }

        function closeCompliancePlanModal() {
            compliancePlanModal.style.display = "none";
            document.getElementById("compliancePlanToggle").checked = false;
        }

        function renderCompliancePlanTable() {
            if (!compliancePlanState.rows.length) {
                compliancePlanEditor.innerHTML = `<div class="empty-hint">ارفع ملف إكسل لبدء التحرير.</div>`;
                return;
            }
            const headers = compliancePlanState.headers;
            const rows = compliancePlanState.rows;
            let thead = "<tr>";
            headers.forEach((h) => {
                thead += `<th>${escapeHtml(h || "")}</th>`;
            });
            thead += "</tr>";
            let tbody = "";
            rows.forEach((row, rIdx) => {
                tbody += "<tr>";
                headers.forEach((_h, cIdx) => {
                    const key = `${rIdx},${cIdx}`;
                    const bg = compliancePlanState.styles[key] || "";
                    const active = compliancePlanState.selectedCell === key ? "outline:2px solid #1d4ed8;" : "";
                    const styleAttr = `${bg ? `background:${bg};` : ""}${active}`;
                    tbody += `<td contenteditable="true" data-r="${rIdx}" data-c="${cIdx}" style="${styleAttr}">${escapeHtml(
                        String(row[cIdx] ?? "")
                    )}</td>`;
                });
                tbody += "</tr>";
            });
            compliancePlanEditor.innerHTML = `<table class="audit-table"><thead>${thead}</thead><tbody>${tbody}</tbody></table>`;
            const highlightSelected = () => {
                const selected = compliancePlanState.selectedCell;
                compliancePlanEditor.querySelectorAll("td[data-r][data-c]").forEach((cell) => {
                    const key = `${cell.dataset.r},${cell.dataset.c}`;
                    cell.style.outline = selected === key ? "2px solid #1d4ed8" : "";
                });
            };
            compliancePlanEditor.querySelectorAll("td").forEach((td) => {
                td.addEventListener("click", () => {
                    const r = Number(td.dataset.r);
                    const c = Number(td.dataset.c);
                    compliancePlanState.selectedCell = `${r},${c}`;
                    highlightSelected();
                });
                td.addEventListener("input", () => {
                    const r = Number(td.dataset.r);
                    const c = Number(td.dataset.c);
                    compliancePlanState.rows[r][c] = td.textContent || "";
                });
            });
            highlightSelected();
        }

        function loadComplianceSheet(sheetName) {
            if (!complianceWorkbook || !sheetName) return;
            const ws = complianceWorkbook.Sheets[sheetName];
            const aoa = XLSX.utils.sheet_to_json(ws, { header: 1, defval: "" });
            const headers = (aoa[0] || []).map((x) => String(x ?? "").trim());
            const rows = aoa.slice(1).map((r) => headers.map((_h, i) => String(r[i] ?? "")));
            compliancePlanState.sheetName = sheetName;
            compliancePlanState.headers = headers;
            compliancePlanState.rows = rows;
            compliancePlanState.styles = {};
            compliancePlanState.selectedCell = null;
            renderCompliancePlanTable();
        }

        compliancePlanFileInput.addEventListener("change", async () => {
            const f = compliancePlanFileInput.files && compliancePlanFileInput.files[0];
            if (!f) return;
            const buff = await f.arrayBuffer();
            complianceWorkbook = XLSX.read(buff, { type: "array" });
            compliancePlanSheetSelect.innerHTML = "";
            (complianceWorkbook.SheetNames || []).forEach((s, idx) => {
                const opt = document.createElement("option");
                opt.value = s;
                opt.textContent = s;
                if (idx === 0) opt.selected = true;
                compliancePlanSheetSelect.appendChild(opt);
            });
            loadComplianceSheet(compliancePlanSheetSelect.value);
        });

        compliancePlanSheetSelect.addEventListener("change", () => loadComplianceSheet(compliancePlanSheetSelect.value));
        document.getElementById("compliancePlanApplyColorBtn").addEventListener("click", () => {
            if (!compliancePlanState.selectedCell) return;
            compliancePlanState.styles[compliancePlanState.selectedCell] = compliancePlanColorInput.value;
            renderCompliancePlanTable();
        });
        document.getElementById("compliancePlanClearColorBtn").addEventListener("click", () => {
            if (!compliancePlanState.selectedCell) return;
            delete compliancePlanState.styles[compliancePlanState.selectedCell];
            renderCompliancePlanTable();
        });

        document.getElementById("compliancePlanSaveHtmlBtn").addEventListener("click", async () => {
            await downloadInteractiveSnapshot();
        });
        document.getElementById("compliancePlanModalClose").addEventListener("click", closeCompliancePlanModal);
        compliancePlanModal.addEventListener("click", (event) => {
            if (event.target === compliancePlanModal) closeCompliancePlanModal();
        });
        document.getElementById("compliancePlanToggle").addEventListener("change", (event) => {
            if (event.target.checked) {
                compliancePlanModal.style.display = "flex";
                renderCompliancePlanTable();
            } else {
                closeCompliancePlanModal();
            }
        });
        const finalStatusToggle = document.getElementById("finalStatusToggle");
        if (finalStatusToggle) {
            finalStatusToggle.addEventListener("change", (event) => {
                if (event.target.checked) {
                    openRecordList("تقرير تتبع حالة الالتزام السنوي", { final_status_change: "1" });
                } else {
                    closeRecordList();
                }
            });
        }
        const assessmentNewToggle = document.getElementById("assessmentNewToggle");
        if (assessmentNewToggle) {
            assessmentNewToggle.addEventListener("change", (event) => {
                if (event.target.checked) {
                    openRecordList("نتائج تقييم خلال السنة الحالية", { assessment_new: "1" });
                } else {
                    closeRecordList();
                }
            });
        }
        const annualTrackingWordBtn = document.getElementById("annualTrackingWordBtn");
        if (annualTrackingWordBtn) {
            annualTrackingWordBtn.addEventListener("click", () => {
                downloadRecordListWord();
            });
        }
        const assessmentGenerateBtn = document.getElementById("assessmentGenerateBtn");
        if (assessmentGenerateBtn) {
            assessmentGenerateBtn.addEventListener("click", () => {
                generateAssessmentForms();
            });
        }
        const assessmentFormsClose = document.getElementById("assessmentFormsClose");
        if (assessmentFormsClose) {
            assessmentFormsClose.addEventListener("click", closeAssessmentForms);
        }
        const assessmentDownloadWordBtn = document.getElementById("assessmentDownloadWordBtn");
        if (assessmentDownloadWordBtn) {
            assessmentDownloadWordBtn.addEventListener("click", () => {
                downloadAssessmentWord();
            });
        }
        const assessmentFormsModal = document.getElementById("assessmentFormsModal");
        if (assessmentFormsModal) {
            assessmentFormsModal.addEventListener("click", (event) => {
                if (event.target === assessmentFormsModal) {
                    closeAssessmentForms();
                }
            });
        }
        restoreCompliancePlanState();
        try {
            localStorage.removeItem("compliancePlanEditor.v1");
        } catch (_e) {}
        renderCompliancePlanTable();

        async function fetchSummary() {
            const clearBtn = document.getElementById("clearFiltersBtn");
            clearBtn.disabled = true;
            const qs = buildFilterQueryString(state);
            if (summaryFetchController) {
                summaryFetchController.abort();
            }
            summaryFetchController = new AbortController();
            let response;
            let data;
            try {
                response = await fetch(`${arApiUrl('/summary')}?${qs.toString()}`, {
                    signal: summaryFetchController.signal,
                    credentials: "same-origin"
                });
                data = await response.json();
            } catch (err) {
                if (err && err.name === "AbortError") {
                    return;
                }
                clearBtn.disabled = false;
                throw err;
            } finally {
                summaryFetchController = null;
            }

            if (!response.ok) {
                alert("تعذر تحميل بيانات التحليل. ارفع الملف مرة أخرى.");
                window.location.href = "/";
                return;
            }

            window.currentTotal = data.total;
            window.lastSummaryData = data;
            pruneStaleFilters(data);
            renderComplianceStatusRow(data);
            renderSubsidiaryCompanyPanel(data);
            renderFilterGroups(data);
            updateTopCharts(data);
            renderFieldBoxes(data);
            renderFieldOptions(data);
            await updateBrandLogo();
            Object.keys(standaloneSelectMeta).forEach((stateKey) => {
                renderStandaloneSelect(stateKey, data.groups[standaloneSelectMeta[stateKey].apiKey] || []);
            });
            clearBtn.disabled = false;
            if (document.getElementById("agingToggle")?.checked && isAgingModalOpen()) {
                await refreshAgingSummary();
            }
            if (document.getElementById("planStatusToggle")?.checked && isPlanStatusOpen()) {
                await refreshPlanStatusReport();
            }
            if (document.getElementById("programStatusToggle")?.checked && isProgramStatusOpen()) {
                await refreshProgramStatusReport();
            }
            // no-op: compliance plan editor is local (no server refresh required)
        }

        function renderStandaloneSelect(stateKey, items) {
            const meta = standaloneSelectMeta[stateKey];
            const current = state[stateKey];
            if (stateKey !== "legal_text") {
                return;
            }
            const dropdown = document.getElementById("legalTextDropdown");
            const menu = document.getElementById("legalTextDropdownMenu");
            const btn = document.getElementById("legalTextDropdownBtn");
            menu.innerHTML = "";
            const tools = document.createElement("div");
            tools.className = "legal-menu-tools";
            tools.innerHTML = `
                <input id="legalSearchInput" class="legal-search" type="text" placeholder="بحث داخل النص النظامي..." />
                <div class="legal-actions">
                    <button id="legalClearBtn" type="button" class="legal-clear-btn">مسح التحديد</button>
                    <span id="legalVisibleCount" class="legal-count"></span>
                </div>
            `;
            menu.appendChild(tools);
            const searchInput = tools.querySelector("#legalSearchInput");
            const clearBtn = tools.querySelector("#legalClearBtn");
            const visibleCount = tools.querySelector("#legalVisibleCount");
            const listContainer = document.createElement("div");
            menu.appendChild(listContainer);

            const allRow = document.createElement("label");
            allRow.className = "legal-option" + (current.length === 0 ? " selected-option" : "");
            allRow.innerHTML = `<input type="checkbox" ${current.length === 0 ? "checked" : ""} /><span>الكل</span>`;
            allRow.addEventListener("click", (event) => {
                event.preventDefault();
                state.legal_text.length = 0;
                fetchSummary();
                closeLegalDropdown();
            });
            listContainer.appendChild(allRow);

            items = withoutBlankItems(items);
            const rows = [];
            const listFrag = document.createDocumentFragment();
            items.forEach((item) => {
                const row = document.createElement("label");
                row.className = "legal-option" + (current.includes(item.key) ? " selected-option" : "");
                row.dataset.label = String(item.label || "").toLowerCase();
                row.innerHTML = `
                    <input type="checkbox" ${current.includes(item.key) ? "checked" : ""} />
                    <span>${item.label}</span>
                    <span class="legal-option-count">(${toEnglishNumber(item.count)})</span>
                `;
                row.title = String(item.label || "");
                row.addEventListener("click", (event) => {
                    event.preventDefault();
                    // اختيار نص واحد فقط لكل نقرة: ينتقل التفاصيل فوراً بين النصوص ولا يبقى وضع «نصّان محددان» يغلق النافذة أو يربك الفلتر.
                    const keyStr = String(item.key);
                    const sole = state.legal_text.length === 1 ? String(state.legal_text[0]) : null;
                    if (sole === keyStr) {
                        state.legal_text.length = 0;
                        fetchSummary();
                        closeLegalModal();
                        return;
                    }
                    state.legal_text.length = 0;
                    state.legal_text.push(item.key);
                    fetchSummary();
                    openLegalDetails(item.key);
                });
                rows.push(row);
                listFrag.appendChild(row);
            });
            listContainer.appendChild(listFrag);

            const updateVisibleCount = () => {
                const v = rows.filter((r) => r.style.display !== "none").length;
                visibleCount.textContent = `المعروض: ${toEnglishNumber(v)} / ${toEnglishNumber(items.length)}`;
            };
            searchInput.addEventListener("input", () => {
                const q = String(searchInput.value || "").trim().toLowerCase();
                rows.forEach((r) => {
                    r.style.display = !q || r.dataset.label.includes(q) ? "" : "none";
                });
                updateVisibleCount();
            });
            clearBtn.addEventListener("click", () => {
                state.legal_text.length = 0;
                fetchSummary();
            });
            updateVisibleCount();
            if (current.length) {
                btn.innerHTML = `<span class="legal-btn-main">النصوص المحددة</span><span class="legal-btn-sub">محدد (${toEnglishNumber(
                    current.length
                )})</span>`;
            } else {
                btn.innerHTML = `<span class="legal-btn-main">النصوص النظامية</span><span class="legal-btn-sub">الكل (${toEnglishNumber(
                    items.length
                )})</span>`;
            }
        }

        function closeLegalDropdown() {
            const dropdown = document.getElementById("legalTextDropdown");
            dropdown.classList.remove("open");
        }

        const legalModal = document.getElementById("legalModal");
        const legalModalDetailMount = document.getElementById("legalModalDetailMount");
        function setLegalModalMainContent(html) {
            if (legalModalDetailMount) {
                legalModalDetailMount.innerHTML = html;
            }
        }
        const legalModalTitle = document.getElementById("legalModalTitle");
        const legalModalTextPanel = document.getElementById("legalModalTextPanel");
        const legalModalFullText = document.getElementById("legalModalFullText");
        const legalModalLegislator = document.getElementById("legalModalLegislator");
        const legalModalLegislatorValue = document.getElementById("legalModalLegislatorValue");
        function setLegalModalLegislator(value) {
            if (!legalModalLegislator || !legalModalLegislatorValue) {
                return;
            }
            const t = value == null ? "" : String(value).trim();
            if (!t || t === "—") {
                legalModalLegislator.hidden = true;
                legalModalLegislatorValue.textContent = "—";
                return;
            }
            legalModalLegislator.hidden = false;
            legalModalLegislatorValue.textContent = t;
        }
        function setLegalModalTitleText(text, loading) {
            legalModalTitle.textContent = "النص النظامي";
            legalModalTitle.removeAttribute("title");
            if (!legalModalTextPanel || !legalModalFullText) {
                return;
            }
            if (loading) {
                legalModalTextPanel.hidden = true;
                legalModalFullText.textContent = "—";
                setLegalModalLegislator("");
                return;
            }
            const t = text == null ? "" : String(text).trim();
            if (!t) {
                legalModalTextPanel.hidden = true;
                legalModalFullText.textContent = "—";
                return;
            }
            legalModalTextPanel.hidden = false;
            legalModalFullText.textContent = t;
        }
        const legalModalDownloadWord = document.getElementById("legalModalDownloadWord");
        const isSnapshotPackPage = !!document.getElementById("snapshot-pack");
        let legalModalCurrentText = "";

        function setLegalModalWordEnabled(enabled) {
            if (!legalModalDownloadWord) {
                return;
            }
            legalModalDownloadWord.disabled = !enabled;
        }

        function dashboardCsrfToken() {
            const m = document.cookie.match(/(?:^|;)\s*csrftoken=([^;]+)/);
            return m ? decodeURIComponent(m[1]) : "";
        }

        function downloadLegalTextWordHtml(text, fields) {
            const logoSrc = currentBrandLogoSrc();
            const logoHtml = logoSrc
                ? `<img src="${escapeHtml(logoSrc)}" alt="" style="height:52px;max-width:180px;object-fit:contain;">`
                : "";
            const list = fields || [];
            const legislator = list.find((f) => f.label === "المشرع");
            const rows = list.filter((f) => {
                const label = String(f.label || "").trim();
                const value = String(f.value || "").trim();
                if (label === "المشرع") {
                    return false;
                }
                return value && value !== "—" && value !== "-" && value !== "(blank)";
            }).map((f) => `<tr><td class="lbl">${escapeHtml(f.label)}</td><td>${escapeHtml(f.value)}</td></tr>`).join("");
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>النص النظامي</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; color: #1e293b; }
  .brand { display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid #1F4E79; padding-bottom: 10px; margin-bottom: 14px; }
  .kicker { color: #1F4E79; font-weight: 800; margin: 0; font-size: 12pt; }
  h1 { color: #1F4E79; font-size: 20pt; margin: 8px 0 12px; }
  .leg { font-weight: 800; color: #1F4E79; margin: 0 0 12px; }
  .body { font-size: 12pt; line-height: 1.7; margin: 0 0 16px; white-space: pre-wrap; }
  table { width: 100%; border-collapse: collapse; font-size: 11pt; }
  th, td { border: 1px solid #9aa5b1; padding: 8px 10px; vertical-align: top; }
  th { background: #1F4E79; color: #fff; }
  .lbl { background: #EEF2FF; font-weight: 800; color: #1F4E79; width: 28%; }
</style>
</head>
<body>
  <div class="brand">${logoHtml}<p class="kicker">إدارة الالتزام</p></div>
  <h1>النص النظامي</h1>
  ${legislator && legislator.value ? `<p class="leg">المشرع: ${escapeHtml(legislator.value)}</p>` : ""}
  <p class="body">${escapeHtml(text || "—")}</p>
  ${rows ? `<table><thead><tr><th>الحقل</th><th>القيمة</th></tr></thead><tbody>${rows}</tbody></table>` : ""}
</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "النص-النظامي.doc";
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        function closeLegalModal() {
            legalModal.style.display = "none";
            if (legalModalDetailMount) {
                legalModalDetailMount.innerHTML = "";
            }
            setLegalModalWordEnabled(false);
            setLegalModalLegislator("");
            setLegalModalTitleText("", true);
        }

        document.getElementById("legalModalClose").addEventListener("click", closeLegalModal);
        const recordListModal = document.getElementById("recordListModal");
        const recordListClose = document.getElementById("recordListClose");
        const recordListSearch = document.getElementById("recordListSearch");
        if (recordListClose) {
            recordListClose.addEventListener("click", closeRecordList);
        }
        if (recordListModal) {
            recordListModal.addEventListener("click", (event) => {
                if (event.target === recordListModal) {
                    closeRecordList();
                }
            });
        }
        if (recordListSearch) {
            recordListSearch.addEventListener("input", () => {
                renderRecordListRows(recordListSearch.value);
            });
        }
        if (legalModalDownloadWord) {
            legalModalDownloadWord.addEventListener("click", async () => {
                const t = legalModalCurrentText;
                if (!t) {
                    return;
                }
                legalModalDownloadWord.disabled = true;
                const cached = legalDetailsCache.get(t) || {};
                const fields = cached.fields || [];
                try {
                    const isLive = Boolean((window.__AR_DASHBOARD__ || {}).isLive);
                    if (isLive) {
                        const token = dashboardCsrfToken();
                        const headers = { "Content-Type": "application/json" };
                        if (token) {
                            headers["X-CSRFToken"] = token;
                        }
                        const response = await fetch(arApiUrl("/export-legal-text-docx"), {
                            method: "POST",
                            credentials: "same-origin",
                            headers,
                            body: JSON.stringify({ text: t, fields })
                        });
                        if (response.ok) {
                            const blob = await response.blob();
                            let fname = "النص-النظامي.docx";
                            const cd = response.headers.get("Content-Disposition") || "";
                            const m = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(cd);
                            if (m && m[1]) {
                                fname = decodeURIComponent(m[1].trim());
                                if (!/\.docx$/i.test(fname)) {
                                    fname = `${fname}.docx`;
                                }
                            }
                            const a = document.createElement("a");
                            a.href = URL.createObjectURL(blob);
                            a.download = fname;
                            a.click();
                            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
                            return;
                        }
                    }
                    downloadLegalTextWordHtml(t, fields);
                } catch (_err) {
                    downloadLegalTextWordHtml(t, fields);
                } finally {
                    setLegalModalWordEnabled(!!legalModalCurrentText);
                }
            });
        }
        legalModal.addEventListener("click", (event) => {
            if (event.target === legalModal) {
                closeLegalModal();
            }
        });
        document.addEventListener("keydown", (event) => {
            if (event.key !== "Escape") {
                return;
            }
            if (legalModal && legalModal.style.display === "flex") {
                closeLegalModal();
                return;
            }
            if (isRecordListOpen()) {
                closeRecordList();
                return;
            }
            if (isAgingModalOpen()) {
                closeAgingModal();
                return;
            }
            if (isPlanStatusOpen()) {
                closePlanStatusModal();
                return;
            }
            if (isProgramStatusOpen()) {
                closeProgramStatusModal();
                return;
            }
            if (isFileStudioOpen()) {
                closeFileStudio();
            }
        });

        const agingModal = document.getElementById("agingModal");
        const agingModalBody = document.getElementById("agingModalBody");
        const agingModalTitle = document.getElementById("agingModalTitle");

        let agingOverYearExpanded = false;

        function isAgingModalOpen() {
            return agingModal && agingModal.style.display === "flex";
        }

        function selectedAgingDateSource() {
            return "target";
        }

        function closeAgingModal() {
            agingModal.style.display = "none";
            agingModalBody.innerHTML = "";
            const toggle = document.getElementById("agingToggle");
            if (toggle) toggle.checked = false;
        }

        function openAgingRecords(timeId, riskId, title) {
            const refInput = document.getElementById("agingReferenceDate");
            const extra = {
                aging_time: timeId || "all",
                reference: refInput && refInput.value ? refInput.value : ""
            };
            if (riskId) {
                extra.aging_risk = riskId;
            }
            openRecordList(title || "سجلات التقادم", extra);
        }

        function agingCountCell(value, timeId, riskId, title) {
            const n = Number(value || 0);
            if (!n) {
                return `<td></td>`;
            }
            const t = escapeHtml(title || "");
            return `<td class="aging-count-cell${riskId ? "" : " total-col"}" data-aging-time="${escapeHtml(timeId)}" data-aging-risk="${escapeHtml(riskId || "")}" data-aging-title="${t}" title="عرض السجلات">${toEnglishNumber(n)}</td>`;
        }

        function renderAgingMatrix(data) {
            const riskCols = data.risk_columns || [];
            const timeRows = data.time_rows || [];
            const overYearRows = data.over_year_rows || [];
            const colTotals = data.column_totals || {};

            let head = `<th class="time-col">الفترة الزمنية</th>`;
            riskCols.forEach((rc) => {
                const bg = rc.color || "";
                const fg = rc.text_color || "#ffffff";
                const cls = `aging-risk-${rc.id}`;
                const style = bg ? ` style="background:${bg};color:${fg};"` : "";
                head += `<th class="${cls}"${style}>${escapeHtml(rc.label)}</th>`;
            });
            head += `<th class="total-col">المجموع</th>`;

            const rowHtml = (tr, extraClass) => {
                const riskLabel = (id) => {
                    const rc = riskCols.find((x) => x.id === id);
                    return rc ? rc.label : id;
                };
                let html = `<tr class="${extraClass || ""}">`;
                if (tr.id === "ge_1y") {
                    const caret = agingOverYearExpanded ? "▼" : "▶";
                    html += `<td class="time-col aging-expand-cell" data-aging-expand="1"><span class="aging-expand-label"><span class="aging-expand-caret">${caret}</span> ${escapeHtml(tr.label)}</span></td>`;
                } else {
                    html += `<td class="time-col">${escapeHtml(tr.label)}</td>`;
                }
                riskCols.forEach((rc) => {
                    const v = tr.cells[rc.id] ?? 0;
                    html += agingCountCell(v, tr.id, rc.id, `${tr.label} · ${riskLabel(rc.id)}`);
                });
                html += agingCountCell(tr.total, tr.id, "", `${tr.label} · كل التصنيفات`);
                html += `</tr>`;
                return html;
            };

            let body = "";
            timeRows.forEach((tr) => {
                body += rowHtml(tr, tr.id === "ge_1y" ? "aging-row-expandable" : "");
                if (tr.id === "ge_1y" && agingOverYearExpanded) {
                    overYearRows.forEach((child) => {
                        body += rowHtml(child, "aging-row-child");
                    });
                }
            });

            let foot = `<tr><td class="time-col">المجموع</td>`;
            riskCols.forEach((rc) => {
                const v = colTotals[rc.id] ?? 0;
                foot += agingCountCell(v, "all", rc.id, `كل الفترات · ${rc.label}`);
            });
            foot += agingCountCell(data.grand_total, "all", "", "كل السجلات في التقادم");
            foot += `</tr>`;

            return `<table class="aging-matrix"><thead><tr>${head}</tr></thead><tbody>${body}</tbody><tfoot>${foot}</tfoot></table>`;
        }

        function paintAgingModal(data) {
            window.lastAgingExport = data;
            agingModalTitle.textContent = `ملخص التقادم (حتى ${data.reference})`;
            agingModalBody.innerHTML = `<div class="aging-matrix-wrap">${renderAgingMatrix(data)}</div>`;
            const table = agingModalBody.querySelector(".aging-matrix");
            if (table) {
                table.addEventListener("click", (event) => {
                    const expand = event.target.closest("[data-aging-expand]");
                    if (expand) {
                        event.preventDefault();
                        agingOverYearExpanded = !agingOverYearExpanded;
                        paintAgingModal(data);
                        return;
                    }
                    const cell = event.target.closest(".aging-count-cell");
                    if (!cell) {
                        return;
                    }
                    openAgingRecords(cell.dataset.agingTime, cell.dataset.agingRisk, cell.dataset.agingTitle);
                });
            }
        }

        async function refreshAgingSummary() {
            const refInput = document.getElementById("agingReferenceDate");
            const ref = refInput.value;
            const source = selectedAgingDateSource();
            if (!ref || !source) {
                return;
            }
            agingModalBody.innerHTML = `<div class="empty-hint">جاري التحميل...</div>`;
            const qs = buildFilterQueryString(state);
            qs.set("reference", ref);
            qs.set("aging_date_source", source);
            const response = await fetch(`${arApiUrl('/aging-summary')}?${qs.toString()}`);
            const data = await response.json();
            if (!response.ok) {
                agingModalBody.innerHTML = `<div class="empty-hint">تعذر حساب ملخص التقادم.</div>`;
                return;
            }
            paintAgingModal(data);
        }

        function agingCountDisplay(value) {
            const n = Number(value || 0);
            return n ? toEnglishNumber(n) : "";
        }

        function downloadAgingWordHtml(data) {
            if (!data) {
                return;
            }
            const logoSrc = currentBrandLogoSrc();
            const logoHtml = logoSrc
                ? `<img src="${escapeHtml(logoSrc)}" alt="" style="height:52px;max-width:180px;object-fit:contain;">`
                : "";
            const riskCols = data.risk_columns || [];
            const timeRows = data.time_rows || [];
            const overYearRows = data.over_year_rows || [];
            const colTotals = data.column_totals || {};
            const colSpan = 2 + riskCols.length;
            const title = data.reference ? `ملخص التقادم (حتى ${data.reference})` : "ملخص التقادم";
            const riskHeads = riskCols.map((rc) => {
                const bg = rc.color || "#7b8794";
                const fg = rc.text_color || "#ffffff";
                return `<th style="background:${escapeHtml(bg)};color:${escapeHtml(fg)};">${escapeHtml(rc.label || "")}</th>`;
            }).join("");
            const rowHtml = (tr, child) => {
                const timeStyle = child
                    ? "background:#f0f9ff;color:#1e3a8a;text-align:right;"
                    : "background:#e0f2fe;color:#0f172a;text-align:right;";
                const cells = riskCols.map((rc) => `<td>${agingCountDisplay(tr.cells && tr.cells[rc.id])}</td>`).join("");
                return `<tr>
                    <td style="${timeStyle}">${escapeHtml(tr.label || "")}</td>
                    ${cells}
                    <td class="total">${agingCountDisplay(tr.total)}</td>
                </tr>`;
            };
            let body = "";
            timeRows.forEach((tr) => {
                body += rowHtml(tr, false);
                if (tr.id === "ge_1y" && agingOverYearExpanded) {
                    overYearRows.forEach((child) => {
                        body += rowHtml(child, true);
                    });
                }
            });
            const footCells = riskCols.map((rc) => `<td class="total">${agingCountDisplay(colTotals[rc.id])}</td>`).join("");
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; color: #1e293b; }
  .brand { display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid #1F4E79; padding-bottom: 10px; margin-bottom: 14px; }
  .kicker { color: #1F4E79; font-weight: 800; margin: 0; font-size: 12pt; }
  h1 { color: #1F4E79; font-size: 20pt; margin: 8px 0 16px; }
  table { width: 100%; border-collapse: collapse; font-size: 11pt; }
  th, td { border: 1px solid #9aa5b1; padding: 8px 10px; text-align: center; font-weight: 700; }
  th.time { background: #BFDBFE; color: #0f172a; }
  td.total, th.total { background: #3b82f6; color: #fff; }
</style>
</head>
<body>
  <div class="brand">${logoHtml}<p class="kicker">إدارة الالتزام</p></div>
  <h1>${escapeHtml(title)}</h1>
  <table>
    <thead>
      <tr>
        <th class="time">الفترة الزمنية</th>
        ${riskHeads}
        <th class="total">المجموع</th>
      </tr>
    </thead>
    <tbody>${body || `<tr><td colspan="${colSpan}">لا توجد بيانات.</td></tr>`}</tbody>
    <tfoot>
      <tr>
        <td style="background:#e0f2fe;text-align:right;">المجموع</td>
        ${footCells}
        <td class="total">${agingCountDisplay(data.grand_total)}</td>
      </tr>
    </tfoot>
  </table>
</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "ملخص-التقادم.doc";
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        async function downloadAgingWord() {
            const btn = document.getElementById("agingDownloadWordBtn");
            const data = window.lastAgingExport;
            if (btn) {
                btn.disabled = true;
            }
            try {
                const isLive = Boolean((window.__AR_DASHBOARD__ || {}).isLive);
                if (isLive) {
                    const qs = buildFilterQueryString(state);
                    const refInput = document.getElementById("agingReferenceDate");
                    if (refInput && refInput.value) {
                        qs.set("reference", refInput.value);
                    }
                    qs.set("aging_date_source", selectedAgingDateSource());
                    if (agingOverYearExpanded) {
                        qs.set("expand_over_year", "1");
                    }
                    const response = await fetch(`${arApiUrl("/export-aging-docx")}?${qs.toString()}`, {
                        credentials: "same-origin"
                    });
                    if (response.ok) {
                        const blob = await response.blob();
                        const a = document.createElement("a");
                        a.href = URL.createObjectURL(blob);
                        a.download = "ملخص-التقادم.docx";
                        a.click();
                        setTimeout(() => URL.revokeObjectURL(a.href), 1500);
                        return;
                    }
                }
                downloadAgingWordHtml(data);
            } catch (_err) {
                downloadAgingWordHtml(data);
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        document.getElementById("agingModalClose").addEventListener("click", closeAgingModal);
        const agingDownloadWordBtn = document.getElementById("agingDownloadWordBtn");
        if (agingDownloadWordBtn) {
            agingDownloadWordBtn.addEventListener("click", () => {
                downloadAgingWord();
            });
        }
        agingModal.addEventListener("click", (event) => {
            if (event.target === agingModal) {
                closeAgingModal();
            }
        });

        (function initAgingReferenceDate() {
            const el = document.getElementById("agingReferenceDate");
            if (el && !el.value) {
                el.value = new Date().toISOString().slice(0, 10);
            }
        })();

        document.getElementById("agingToggle").addEventListener("change", async (event) => {
            if (event.target.checked) {
                agingModal.style.display = "flex";
                await refreshAgingSummary();
            } else {
                closeAgingModal();
            }
        });

        document.getElementById("agingReferenceDate").addEventListener("change", async () => {
            const toggle = document.getElementById("agingToggle");
            if (toggle && toggle.checked && isAgingModalOpen()) {
                await refreshAgingSummary();
            }
            if (document.getElementById("planStatusToggle")?.checked && isPlanStatusOpen()) {
                await refreshPlanStatusReport();
            }
            refreshLegalModalAgingDays();
        });

        const planStatusModal = document.getElementById("planStatusModal");
        const planStatusBody = document.getElementById("planStatusBody");
        let lastPlanStatusPayload = null;
        let planStatusQuery = "";

        function isPlanStatusOpen() {
            return !!(planStatusModal && planStatusModal.style.display === "flex");
        }

        function closePlanStatusModal() {
            if (planStatusModal) {
                planStatusModal.style.display = "none";
            }
            const toggle = document.getElementById("planStatusToggle");
            if (toggle) {
                toggle.checked = false;
            }
            const search = document.getElementById("planStatusSearch");
            if (search) {
                search.value = "";
            }
            planStatusQuery = "";
        }

        function planStatusCountText(value) {
            const n = Number(value || 0);
            return n ? toEnglishNumber(n) : "";
        }

        function planStatusDeptParam(deptId) {
            return deptId ? String(deptId) : "__none__";
        }

        function openPlanStatusRecords(deptId, bucket, riskId, title) {
            const refInput = document.getElementById("agingReferenceDate");
            const extra = {
                skip_quarters: true,
                plan_dept: planStatusDeptParam(deptId),
                reference: refInput && refInput.value ? refInput.value : ""
            };
            if (bucket) {
                extra.plan_bucket = bucket;
            }
            if (riskId) {
                extra.plan_risk = riskId;
            }
            openRecordList(title || "سجلات خطط المعالجة", extra);
        }

        function planCountCell(value, deptId, bucket, riskId, title) {
            const n = Number(value || 0);
            if (!n) {
                return `<td></td>`;
            }
            return `<td class="plan-status-count" data-plan-dept="${escapeHtml(planStatusDeptParam(deptId))}" data-plan-bucket="${escapeHtml(bucket || "")}" data-plan-risk="${escapeHtml(riskId || "")}" data-plan-title="${escapeHtml(title || "")}" title="عرض السجلات">${planStatusCountText(n)}</td>`;
        }

        function renderPlanStatusTable(data, query) {
            const riskCols = data.risk_columns || [];
            const q = String(query || "").trim().toLowerCase();
            const departments = (data.departments || []).filter((d) => {
                if (!q) {
                    return true;
                }
                return String(d.label || "").toLowerCase().includes(q);
            });
            const totals = data.totals || {};
            const withinHeads = riskCols.map((rc) => {
                const bg = rc.color || "#7b8794";
                const fg = rc.text_color || "#ffffff";
                return `<th class="plan-risk-head" style="background:${escapeHtml(bg)};color:${escapeHtml(fg)};">${escapeHtml(rc.label || "")}</th>`;
            }).join("");
            const groupSpan = riskCols.length + 1;
            let body = "";
            departments.forEach((dept) => {
                const deptId = dept.id || "";
                const withinCells = riskCols.map((rc) =>
                    planCountCell(dept.within && dept.within[rc.id], deptId, "within", rc.id, `${dept.label} · ضمن الجدول · ${rc.label}`)
                ).join("");
                const overdueCells = riskCols.map((rc) =>
                    planCountCell(dept.overdue && dept.overdue[rc.id], deptId, "overdue", rc.id, `${dept.label} · تجاوز الجدول · ${rc.label}`)
                ).join("");
                body += `<tr>
                    <th class="plan-dept-cell" data-plan-dept="${escapeHtml(planStatusDeptParam(deptId))}" data-plan-title="${escapeHtml(dept.label || "")}">${escapeHtml(dept.label || "—")}</th>
                    ${planCountCell(dept.legal_text_count, deptId, "all", "", `${dept.label} · النصوص النظامية`)}
                    ${withinCells}
                    ${planCountCell(dept.within_total, deptId, "within", "", `${dept.label} · ضمن الجدول`)}
                    ${overdueCells}
                    ${planCountCell(dept.overdue_total, deptId, "overdue", "", `${dept.label} · تجاوز الجدول`)}
                </tr>`;
            });
            if (!body) {
                body = `<tr><td class="plan-status-empty" colspan="${2 + groupSpan * 2}">لا توجد خطط مفتوحة مطابقة.</td></tr>`;
            }
            const withinFoot = riskCols.map((rc) => `<td>${planStatusCountText(totals.within && totals.within[rc.id])}</td>`).join("");
            const overdueFoot = riskCols.map((rc) => `<td>${planStatusCountText(totals.overdue && totals.overdue[rc.id])}</td>`).join("");
            return `<div class="plan-status-table-wrap">
                <table class="plan-status-table" dir="rtl">
                    <thead>
                        <tr>
                            <th class="plan-corner" rowspan="2">الادارة او الجهة المعنية</th>
                            <th class="plan-corner" rowspan="2">عدد النصوص النظامية</th>
                            <th class="plan-group plan-group-within" colspan="${groupSpan}">مفتوحة ضمن الجدول الزمني</th>
                            <th class="plan-group plan-group-overdue" colspan="${groupSpan}">مفتوحة تجاوزت الجدول الزمني</th>
                        </tr>
                        <tr>
                            ${withinHeads}
                            <th class="plan-total-head">الاجمالي</th>
                            ${withinHeads}
                            <th class="plan-total-head">الاجمالي</th>
                        </tr>
                    </thead>
                    <tbody>${body}</tbody>
                    <tfoot>
                        <tr>
                            <th>الاجمالي</th>
                            <td>${planStatusCountText(totals.legal_text_count)}</td>
                            ${withinFoot}
                            <td class="plan-total-foot">${planStatusCountText(totals.within_total)}</td>
                            ${overdueFoot}
                            <td class="plan-total-foot">${planStatusCountText(totals.overdue_total)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>`;
        }

        function paintPlanStatusModal(data) {
            lastPlanStatusPayload = data;
            const titleEl = document.getElementById("planStatusTitle");
            const metaEl = document.getElementById("planStatusMeta");
            const kpis = document.getElementById("planStatusKpis");
            if (titleEl) {
                titleEl.textContent = data.title || "حالة خطط المعالجة والإجراءات التصحيحية المتفق عليها مع الإدارة";
            }
            if (metaEl) {
                const ref = data.reference ? `حتى ${data.reference}` : "";
                metaEl.textContent = ref ? `تاريخ المرجع ${ref}` : "";
            }
            if (kpis) {
                kpis.hidden = false;
                kpis.innerHTML = `
                    <article class="plan-kpi"><span>الإدارات</span><strong>${toEnglishNumber(data.department_count || 0)}</strong></article>
                    <article class="plan-kpi plan-kpi-ok"><span>ضمن الجدول</span><strong>${toEnglishNumber((data.totals && data.totals.within_total) || 0)}</strong></article>
                    <article class="plan-kpi plan-kpi-due"><span>تجاوزت الجدول</span><strong>${toEnglishNumber((data.totals && data.totals.overdue_total) || 0)}</strong></article>
                    <article class="plan-kpi"><span>النصوص النظامية</span><strong>${toEnglishNumber((data.totals && data.totals.legal_text_count) || 0)}</strong></article>`;
            }
            if (planStatusBody) {
                planStatusBody.innerHTML = renderPlanStatusTable(data, planStatusQuery);
                planStatusBody.querySelectorAll(".plan-status-count, .plan-dept-cell").forEach((el) => {
                    el.addEventListener("click", () => {
                        const dept = el.dataset.planDept === "__none__" ? "" : (el.dataset.planDept || "");
                        openPlanStatusRecords(
                            dept,
                            el.dataset.planBucket || "all",
                            el.dataset.planRisk || "",
                            el.dataset.planTitle || ""
                        );
                    });
                });
            }
        }

        async function refreshPlanStatusReport() {
            if (!planStatusBody) {
                return;
            }
            planStatusBody.innerHTML = `<div class="empty-hint">جاري التحميل...</div>`;
            const qs = buildFilterQueryString(state);
            const refInput = document.getElementById("agingReferenceDate");
            if (refInput && refInput.value) {
                qs.set("reference", refInput.value);
            }
            try {
                const response = await fetch(`${arApiUrl("/plan-status-summary")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                const data = await response.json();
                if (!response.ok) {
                    planStatusBody.innerHTML = `<div class="empty-hint">تعذر حساب التقرير.</div>`;
                    return;
                }
                paintPlanStatusModal(data);
            } catch (_err) {
                planStatusBody.innerHTML = `<div class="empty-hint">تعذر حساب التقرير.</div>`;
            }
        }

        function downloadPlanStatusWordHtml(data) {
            if (!data) {
                return;
            }
            const logoSrc = currentBrandLogoSrc();
            const logoHtml = logoSrc
                ? `<img src="${escapeHtml(logoSrc)}" alt="" style="height:52px;max-width:180px;object-fit:contain;">`
                : "";
            const title = data.title || "حالة خطط المعالجة والإجراءات التصحيحية المتفق عليها مع الإدارة";
            const wrap = document.createElement("div");
            wrap.innerHTML = renderPlanStatusTable(data, "");
            const table = wrap.querySelector("table");
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; color: #1e293b; }
  .brand { display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid #1F4E79; padding-bottom: 10px; margin-bottom: 14px; }
  .kicker { color: #1F4E79; font-weight: 800; margin: 0; font-size: 12pt; }
  h1 { color: #1F4E79; font-size: 16pt; margin: 8px 0 16px; text-decoration: underline; }
  table { width: 100%; border-collapse: collapse; font-size: 10pt; }
  th, td { border: 1px solid #9aa5b1; padding: 6px 8px; text-align: center; font-weight: 700; }
  .plan-group-within { background: #3d7a5a; color: #fff; }
  .plan-group-overdue { background: #8f1d2c; color: #fff; }
  .plan-total-head, .plan-total-foot { background: #5b99c9; color: #fff; }
  tfoot th, tfoot td { background: #1f4e79; color: #fff; }
</style>
</head>
<body>
  <div class="brand">${logoHtml}<p class="kicker">إدارة الالتزام</p></div>
  <h1>${escapeHtml(title)}</h1>
  ${table ? table.outerHTML : ""}
</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "حالة-خطط-المعالجة.doc";
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        async function downloadPlanStatusWord() {
            const btn = document.getElementById("planStatusWordBtn");
            const fallback = () => downloadPlanStatusWordHtml(lastPlanStatusPayload);
            try {
                if (btn) {
                    btn.disabled = true;
                }
                const qs = buildFilterQueryString(state);
                const refInput = document.getElementById("agingReferenceDate");
                if (refInput && refInput.value) {
                    qs.set("reference", refInput.value);
                }
                const response = await fetch(`${arApiUrl("/export-plan-status-docx")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                if (!response.ok) {
                    fallback();
                    return;
                }
                const blob = await response.blob();
                const type = (blob.type || "").toLowerCase();
                if (type.includes("json") || blob.size < 80) {
                    fallback();
                    return;
                }
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "حالة-خطط-المعالجة.docx";
                a.click();
                setTimeout(() => URL.revokeObjectURL(a.href), 1500);
            } catch (_err) {
                fallback();
            } finally {
                if (btn) {
                    btn.disabled = false;
                }
            }
        }

        document.getElementById("planStatusClose")?.addEventListener("click", closePlanStatusModal);
        document.getElementById("planStatusWordBtn")?.addEventListener("click", () => {
            downloadPlanStatusWord();
        });
        document.getElementById("planStatusSearch")?.addEventListener("input", (event) => {
            planStatusQuery = event.target.value || "";
            if (lastPlanStatusPayload) {
                paintPlanStatusModal(lastPlanStatusPayload);
            }
        });
        planStatusModal?.addEventListener("click", (event) => {
            if (event.target === planStatusModal) {
                closePlanStatusModal();
            }
        });
        document.getElementById("planStatusToggle")?.addEventListener("change", async (event) => {
            if (event.target.checked) {
                if (planStatusModal) {
                    planStatusModal.style.display = "flex";
                }
                syncReportBrandLogos();
                await refreshPlanStatusReport();
            } else {
                closePlanStatusModal();
            }
        });

        const programStatusModal = document.getElementById("programStatusModal");
        const programStatusBody = document.getElementById("programStatusBody");
        let lastProgramStatusPayload = null;
        let programStatusQuery = "";

        function isProgramStatusOpen() {
            return !!(programStatusModal && programStatusModal.style.display === "flex");
        }

        function closeProgramStatusModal() {
            if (programStatusModal) {
                programStatusModal.style.display = "none";
            }
            const toggle = document.getElementById("programStatusToggle");
            if (toggle) {
                toggle.checked = false;
            }
            const search = document.getElementById("programStatusSearch");
            if (search) {
                search.value = "";
            }
            programStatusQuery = "";
            const sheet = programStatusModal && programStatusModal.querySelector(".program-status-sheet");
            if (sheet) {
                sheet.style.transform = "none";
            }
        }

        function programDeptParam(deptId) {
            return deptId ? String(deptId) : "__none__";
        }

        function programCountText(value) {
            const n = Number(value || 0);
            return n ? toEnglishNumber(n) : "";
        }

        function openProgramStatusRecords(deptId, bucket, title) {
            const extra = {
                skip_quarters: true,
                program_dept: programDeptParam(deptId)
            };
            if (bucket) {
                extra.program_status = bucket;
            }
            openRecordList(title || "متطلبات الالتزام", extra);
        }

        function programCountCell(value, deptId, bucket, title, extraClass) {
            const n = Number(value || 0);
            if (!n) {
                return `<td class="${extraClass || ""}"></td>`;
            }
            return `<td class="program-status-count ${extraClass || ""}" data-program-dept="${escapeHtml(programDeptParam(deptId))}" data-program-status="${escapeHtml(bucket || "all")}" data-program-title="${escapeHtml(title || "")}" title="عرض السجلات">${programCountText(n)}</td>`;
        }

        function renderProgramStatusTable(data, query) {
            const q = String(query || "").trim().toLowerCase();
            const departments = (data.departments || []).filter((d) => {
                if (!q) return true;
                return String(d.label || "").toLowerCase().includes(q);
            });
            const totals = data.totals || {};
            let body = "";
            departments.forEach((dept) => {
                const deptId = dept.id || "";
                body += `<tr>
                    <th class="program-dept-cell" data-program-dept="${escapeHtml(programDeptParam(deptId))}" data-program-status="all" data-program-title="${escapeHtml(dept.label || "")}">${escapeHtml(dept.label || "—")}</th>
                    ${programCountCell(dept.legal_text_count, deptId, "all", `${dept.label} · المتطلبات النظامية`)}
                    ${programCountCell(dept.compliant, deptId, "compliant", `${dept.label} · ملتزم`, "is-ok")}
                    ${programCountCell(dept.noncompliant, deptId, "noncompliant", `${dept.label} · غير ملتزم`, "is-bad")}
                    ${programCountCell(dept.partial, deptId, "partial", `${dept.label} · ملتزم جزئيا`, "is-mid")}
                </tr>`;
            });
            if (!body) {
                body = `<tr><td class="program-status-empty" colspan="5">لا توجد متطلبات مطابقة.</td></tr>`;
            }
            return `<div class="program-status-table-wrap">
                <p class="program-table-caption">ملخص المتطلبات النظامية التي خضعت لبرنامج الالتزام حسب الادارة او الجهة المعنية</p>
                <table class="program-status-table" dir="rtl">
                    <thead>
                        <tr>
                            <th>الادارة او الجهة المعنية</th>
                            <th>عدد المتطلبات النظامية</th>
                            <th class="is-ok">عدد المتطلبات الملتزم بها</th>
                            <th class="is-bad">عدد المتطلبات غير الملتزم بها</th>
                            <th class="is-mid">عدد المتطلبات الملتزم بها جزئيا</th>
                        </tr>
                    </thead>
                    <tbody>${body}</tbody>
                    <tfoot>
                        <tr>
                            <th>الاجمالي</th>
                            <td>${programCountText(totals.legal_text_count)}</td>
                            <td class="is-ok">${programCountText(totals.compliant)}</td>
                            <td class="is-bad">${programCountText(totals.noncompliant)}</td>
                            <td class="is-mid">${programCountText(totals.partial)}</td>
                        </tr>
                    </tfoot>
                </table>
            </div>`;
        }

        let programOverallChoice = "";
        try {
            const saved = localStorage.getItem("arProgramOverallColor");
            if (saved === "red" || saved === "yellow" || saved === "green") {
                programOverallChoice = saved;
            }
        } catch (_err) {
            programOverallChoice = "";
        }

        function programOverallLevel(data) {
            const levels = (data && data.levels) || [];
            const chosen = programOverallChoice || (data && data.overall && data.overall.id) || "green";
            return levels.find((item) => item.id === chosen) || data.overall || { id: "green", label: "أخضر" };
        }

        function setProgramOverallChoice(levelId) {
            const id = String(levelId || "").toLowerCase();
            if (id !== "red" && id !== "yellow" && id !== "green") {
                return;
            }
            programOverallChoice = id;
            try {
                localStorage.setItem("arProgramOverallColor", id);
            } catch (_err) {
                /* ignore */
            }
            if (lastProgramStatusPayload) {
                const levels = lastProgramStatusPayload.levels || [];
                lastProgramStatusPayload.overall = levels.find((item) => item.id === id) || lastProgramStatusPayload.overall;
                paintProgramStatusModal(lastProgramStatusPayload);
            }
        }

        function paintProgramStatusModal(data) {
            lastProgramStatusPayload = data;
            const titleEl = document.getElementById("programStatusTitle");
            const guideEl = document.getElementById("programStatusGuide");
            const legendEl = document.getElementById("programStatusLegend");
            const barEl = document.getElementById("programStatusBar");
            if (titleEl) titleEl.textContent = data.title || "الحالة العامة لبرنامج الالتزام";
            if (guideEl) guideEl.textContent = data.guide || "دليل تصنيف الحالة العامة للبرنامج";
            const levels = data.levels || [];
            const overall = programOverallLevel(data);
            if (legendEl) {
                legendEl.innerHTML = levels.map((level) => `
                    <article class="program-legend-card is-${escapeHtml(level.id)}${level.id === overall.id ? " is-selected" : ""}">
                        <span class="program-legend-dot" aria-hidden="true"></span>
                        <h4>${escapeHtml(level.label || "")}</h4>
                        <p>${escapeHtml(level.text || "")}</p>
                    </article>`).join("");
            }
            if (barEl) {
                barEl.className = `program-overall-bar is-${escapeHtml(overall.id || "green")}`;
                barEl.innerHTML = `
                    <div class="program-overall-label">الحالة العامة لبرنامج الالتزام:</div>
                    <div class="program-overall-select is-${escapeHtml(overall.id || "green")}">
                        <label class="program-overall-select-label" for="programOverallSelect">اختيار الحالة</label>
                        <div class="program-overall-select-wrap">
                            <span class="program-overall-swatch is-${escapeHtml(overall.id || "green")}" aria-hidden="true"></span>
                            <select id="programOverallSelect" class="program-overall-dropdown" aria-label="الحالة العامة لبرنامج الالتزام">
                                ${levels.map((level) => `<option value="${escapeHtml(level.id)}" ${level.id === overall.id ? "selected" : ""}>${escapeHtml(level.label || "")}</option>`).join("")}
                            </select>
                        </div>
                    </div>`;
                const selectEl = document.getElementById("programOverallSelect");
                if (selectEl) {
                    selectEl.addEventListener("change", (event) => {
                        setProgramOverallChoice(event.target.value);
                    });
                }
            }
            if (programStatusBody) {
                programStatusBody.innerHTML = renderProgramStatusTable(data, programStatusQuery);
                programStatusBody.querySelectorAll(".program-status-count, .program-dept-cell").forEach((el) => {
                    el.addEventListener("click", () => {
                        const dept = el.dataset.programDept === "__none__" ? "" : (el.dataset.programDept || "");
                        openProgramStatusRecords(dept, el.dataset.programStatus || "all", el.dataset.programTitle || "");
                    });
                });
            }
            requestAnimationFrame(() => fitProgramStatusPage());
        }

        function fitProgramStatusPage() {
            const overlay = programStatusModal;
            const sheet = overlay && overlay.querySelector(".program-status-sheet");
            if (!overlay || !sheet || overlay.style.display !== "flex") {
                return;
            }
            sheet.style.transform = "none";
            const availW = overlay.clientWidth || window.innerWidth;
            const availH = overlay.clientHeight || window.innerHeight;
            const needW = Math.max(sheet.scrollWidth, sheet.offsetWidth);
            const needH = Math.max(sheet.scrollHeight, sheet.offsetHeight);
            if (!availW || !availH || !needW || !needH) {
                return;
            }
            const scale = Math.min(1, availW / needW, availH / needH);
            sheet.style.transformOrigin = "top center";
            sheet.style.transform = scale < 0.999 ? `scale(${scale})` : "none";
        }

        async function refreshProgramStatusReport() {
            if (!programStatusBody) return;
            programStatusBody.innerHTML = `<div class="empty-hint">جاري التحميل...</div>`;
            const qs = buildFilterQueryString(state);
            try {
                const response = await fetch(`${arApiUrl("/program-status-summary")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                const data = await response.json();
                if (!response.ok) {
                    programStatusBody.innerHTML = `<div class="empty-hint">تعذر حساب التقرير.</div>`;
                    return;
                }
                paintProgramStatusModal(data);
            } catch (_err) {
                programStatusBody.innerHTML = `<div class="empty-hint">تعذر حساب التقرير.</div>`;
            }
        }

        function downloadProgramStatusWordHtml(data) {
            if (!data) return;
            const logoSrc = currentBrandLogoSrc();
            const logoHtml = logoSrc
                ? `<img src="${escapeHtml(logoSrc)}" alt="" style="height:52px;max-width:180px;object-fit:contain;">`
                : "";
            const title = data.title || "الحالة العامة لبرنامج الالتزام";
            const overall = programOverallLevel(data);
            const barHtml = `<table style="width:100%;border-collapse:collapse;margin:12px 0 16px;">
                <tr>
                    <td style="background:#2a6499;color:#fff;font-weight:800;text-align:center;padding:10px;">الحالة العامة لبرنامج الالتزام:</td>
                    <td class="is-${escapeHtml(overall.id || "green")}" style="text-align:center;font-weight:800;padding:10px;">${escapeHtml(overall.label || "")}</td>
                </tr>
            </table>`;
            const wrap = document.createElement("div");
            wrap.innerHTML = `${document.getElementById("programStatusLegend") ? document.getElementById("programStatusLegend").outerHTML : ""}${barHtml}${renderProgramStatusTable(data, "")}`;
            const html = `<!DOCTYPE html>
<html lang="ar" dir="rtl" xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word">
<head>
<meta charset="utf-8">
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: Calibri, Arial, sans-serif; direction: rtl; color: #1e293b; }
  .brand { display: flex; align-items: center; justify-content: space-between; border-bottom: 3px solid #1F4E79; padding-bottom: 10px; margin-bottom: 14px; }
  h1 { color: #1F4E79; font-size: 18pt; margin: 8px 0 6px; text-decoration: underline; }
  .program-legend { display: flex; gap: 10px; }
  .program-legend-card { border: 1px solid #cbd5e1; padding: 10px; width: 32%; }
  .is-green { background: #ecfdf3; }
  .is-yellow { background: #fffbeb; }
  .is-red { background: #fef2f2; }
  table { width: 100%; border-collapse: collapse; font-size: 10pt; }
  th, td { border: 1px solid #94a3b8; padding: 6px 8px; text-align: center; font-weight: 700; }
</style>
</head>
<body>
  <div class="brand">${logoHtml}<p style="color:#1F4E79;font-weight:800;">إدارة الالتزام</p></div>
  <h1>${escapeHtml(title)}</h1>
  ${wrap.innerHTML}
</body>
</html>`;
            const blob = new Blob(["\ufeff", html], { type: "application/msword;charset=utf-8" });
            const a = document.createElement("a");
            a.href = URL.createObjectURL(blob);
            a.download = "الحالة-العامة-لبرنامج-الالتزام.doc";
            a.click();
            setTimeout(() => URL.revokeObjectURL(a.href), 1500);
        }

        async function downloadProgramStatusWord() {
            const btn = document.getElementById("programStatusWordBtn");
            const fallback = () => downloadProgramStatusWordHtml(lastProgramStatusPayload);
            try {
                if (btn) btn.disabled = true;
                const qs = buildFilterQueryString(state);
                if (programOverallChoice) {
                    qs.set("overall", programOverallChoice);
                }
                const response = await fetch(`${arApiUrl("/export-program-status-docx")}?${qs.toString()}`, {
                    credentials: "same-origin"
                });
                if (!response.ok) {
                    fallback();
                    return;
                }
                const blob = await response.blob();
                const type = (blob.type || "").toLowerCase();
                if (type.includes("json") || blob.size < 80) {
                    fallback();
                    return;
                }
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = "الحالة-العامة-لبرنامج-الالتزام.docx";
                a.click();
                setTimeout(() => URL.revokeObjectURL(a.href), 1500);
            } catch (_err) {
                fallback();
            } finally {
                if (btn) btn.disabled = false;
            }
        }

        document.getElementById("programStatusClose")?.addEventListener("click", closeProgramStatusModal);
        document.getElementById("programStatusWordBtn")?.addEventListener("click", () => downloadProgramStatusWord());
        document.getElementById("programStatusSearch")?.addEventListener("input", (event) => {
            programStatusQuery = event.target.value || "";
            if (lastProgramStatusPayload) paintProgramStatusModal(lastProgramStatusPayload);
        });
        programStatusModal?.addEventListener("click", (event) => {
            if (event.target === programStatusModal) closeProgramStatusModal();
        });
        document.getElementById("programStatusToggle")?.addEventListener("change", async (event) => {
            if (event.target.checked) {
                if (programStatusModal) programStatusModal.style.display = "flex";
                syncReportBrandLogos();
                await refreshProgramStatusReport();
            } else {
                closeProgramStatusModal();
            }
        });
        window.addEventListener("resize", () => {
            if (isProgramStatusOpen()) {
                fitProgramStatusPage();
            }
        });

        const legalDetailsCache = new Map();

        function selectedAgingReferenceDate() {
            const el = document.getElementById("agingReferenceDate");
            const raw = el && el.value ? String(el.value).trim() : "";
            const stamp = (raw || new Date().toISOString().slice(0, 10)).slice(0, 10);
            const d = new Date(`${stamp}T12:00:00`);
            return Number.isNaN(d.getTime()) ? null : d;
        }

        function parseDashboardDate(value) {
            const s = String(value || "").trim();
            if (!s || s === "—" || s === "(blank)") {
                return null;
            }
            if (/^-?\d+(?:\.\d+)?$/.test(s)) {
                const n = Number(s);
                if (Number.isFinite(n)) {
                    if (n >= 1e12) {
                        const d = new Date(n);
                        if (!Number.isNaN(d.getTime())) {
                            return new Date(d.getFullYear(), d.getMonth(), d.getDate());
                        }
                    }
                    if (n >= 1e9) {
                        const d = new Date(n * 1000);
                        if (!Number.isNaN(d.getTime())) {
                            return new Date(d.getFullYear(), d.getMonth(), d.getDate());
                        }
                    }
                    if (n >= 20000 && n <= 80000) {
                        const excel = new Date(Date.UTC(1899, 11, 30) + Math.round(n * 86400000));
                        if (!Number.isNaN(excel.getTime())) {
                            return new Date(excel.getUTCFullYear(), excel.getUTCMonth(), excel.getUTCDate());
                        }
                    }
                }
            }
            const d = new Date(`${s.slice(0, 10)}T12:00:00`);
            return Number.isNaN(d.getTime()) ? null : d;
        }

        function agingDaysFromTargetValue(targetValue) {
            const target = parseDashboardDate(targetValue);
            const ref = selectedAgingReferenceDate();
            if (!target || !ref) {
                return null;
            }
            const t = Date.UTC(target.getFullYear(), target.getMonth(), target.getDate());
            const r = Date.UTC(ref.getFullYear(), ref.getMonth(), ref.getDate());
            return Math.round((r - t) / 86400000);
        }

        function legalTargetDateField(fields) {
            return (fields || []).find((f) => {
                const label = String(f.label || "").replace(/\s+/g, " ").trim();
                return label === "تاريخ التصحيح المستهدف";
            });
        }

        function agingDaysCardHtml(fields) {
            const targetField = legalTargetDateField(fields);
            const days = agingDaysFromTargetValue(targetField && targetField.value);
            const ref = selectedAgingReferenceDate();
            const refLabel = ref
                ? `${ref.getFullYear()}-${String(ref.getMonth() + 1).padStart(2, "0")}-${String(ref.getDate()).padStart(2, "0")}`
                : "—";
            let stateClass = "";
            let valueText = "—";
            let statusText = "لا يوجد تاريخ تصحيح مستهدف";
            if (days === 0) {
                stateClass = "is-due";
                valueText = toEnglishNumber(0);
                statusText = "مستحق اليوم";
            } else if (days > 0) {
                stateClass = "is-overdue";
                valueText = toEnglishNumber(days);
                statusText = days === 1 ? "يوم تأخير" : "أيام تأخير";
            } else if (days < 0) {
                stateClass = "is-remaining";
                valueText = toEnglishNumber(Math.abs(days));
                statusText = "متبقي حتى تاريخ التصحيح المستهدف";
            }
            return `
                <article class="detail-card detail-card--aging ${stateClass}">
                    <div class="aging-days-copy">
                        <h4>أيام التقادم</h4>
                        <p class="aging-days-value">${valueText}</p>
                        <p class="aging-days-meta">${escapeHtml(statusText)}</p>
                    </div>
                    <p class="aging-days-meta">تاريخ المرجع: ${escapeHtml(refLabel)}</p>
                </article>`;
        }

        function refreshLegalModalAgingDays() {
            const modal = document.getElementById("legalModal");
            if (!modal || modal.style.display !== "flex" || !legalModalCurrentText) {
                return;
            }
            const cached = legalDetailsCache.get(legalModalCurrentText);
            if (!cached) {
                return;
            }
            renderLegalModalContent(cached.fields, cached.images, false);
        }

        function renderLegalModalContent(fields, images, imagesPending) {
            const list = fields || [];
            const hiddenLabels = new Set([
                "المشرع",
                "ملاحظات الإدارة",
                "ملاحظات الإدارة.1",
                "تاريخ التصحيح السنوي المستهدف",
                "تاريخ التصحيح المستهدف - الربعي",
                "تاريخ التصحيح السنوي الفعلي",
                "تاريخ التصحيح الفعلي - الربعي",
                "تاريخ التصحيح المعدل",
                "تاريخ التصحيح المستهدف المعدل"
            ]);
            const hasValue = (f) => {
                const v = String(f && f.value != null ? f.value : "").trim();
                return Boolean(v) && v !== "—" && v !== "-" && v !== "(blank)";
            };
            const legislator = list.find((f) => f.label === "المشرع");
            setLegalModalLegislator(legislator && legislator.value);
            const rest = list.filter((f) => !hiddenLabels.has(String(f.label || "").trim()) && hasValue(f));
            const dateFields = rest.filter((f) => String(f.label || "").includes("تاريخ"));
            const otherFields = rest.filter((f) => !String(f.label || "").includes("تاريخ"));
            const cardHtml = (f, extraClass) => `
                    <article class="detail-card ${extraClass || ""}">
                        <h4>${escapeHtml(f.label)}</h4>
                        <p>${escapeHtml(f.value)}</p>
                    </article>`;
            const otherHtml = otherFields
                .map((f) =>
                    cardHtml(
                        f,
                        f.label.includes("البنود") || f.label.includes("ملاحظات") || f.label.includes("الخطة")
                            ? "detail-card--wide"
                            : ""
                    )
                )
                .join("");
            const dateHtml = dateFields.map((f) => cardHtml(f, "detail-card--date")).join("");
            const fieldsHtml = `${agingDaysCardHtml(list)}${otherHtml}${dateHtml}`;

            const imagesHtml =
                images && images.length
                    ? `<div class="image-grid">${images
                          .map(
                              (src) => `
                            <div class="image-tile">
                                <img src="${escapeHtml(src)}" alt="embedded" loading="lazy" />
                            </div>`
                          )
                          .join("")}</div>`
                    : imagesPending
                      ? `<p class="empty-hint" id="legalImagesPending">جاري تحميل الصور المرفقة…</p>`
                      : "";

            setLegalModalMainContent(`
                <div class="detail-grid">${fieldsHtml}</div>
                ${imagesHtml}
            `);
        }

        async function openLegalDetails(text) {
            legalModalCurrentText = text;
            legalModal.style.display = "flex";
            setLegalModalTitleText("", true);
            setLegalModalWordEnabled(false);

            if (legalDetailsCache.has(text)) {
                const cached = legalDetailsCache.get(text);
                setLegalModalTitleText(text, false);
                legalModalCurrentText = text;
                renderLegalModalContent(cached.fields, cached.images, false);
                setLegalModalWordEnabled(true);
                return;
            }

            setLegalModalMainContent(`<div class="empty-hint">جاري التحميل...</div>`);

            if (legalDetailsController) {
                legalDetailsController.abort();
            }
            legalDetailsController = new AbortController();
            let response;
            let data;
            try {
                response = await fetch(arApiUrl('/legal-text-details'), {
                    method: "POST",
                    credentials: "same-origin",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text, include_images: false }),
                    signal: legalDetailsController.signal
                });
                data = await response.json();
            } catch (err) {
                if (err && err.name === "AbortError") {
                    return;
                }
                setLegalModalMainContent(`<div class="empty-hint">تعذر تحميل التفاصيل.</div>`);
                return;
            } finally {
                legalDetailsController = null;
            }
            if (!response.ok) {
                setLegalModalMainContent(`<div class="empty-hint">تعذر تحميل التفاصيل.</div>`);
                return;
            }

            setLegalModalTitleText(text, false);
            legalModalCurrentText = text;

            const excelRow = data.excel_row;
            let images = Array.isArray(data.images) ? data.images.filter(Boolean) : [];
            const needsImages = !images.length && typeof excelRow === "number" && excelRow >= 1;
            renderLegalModalContent(data.fields, images, needsImages);

            if (needsImages) {
                try {
                    const ir = await fetch(`${arApiUrl('/legal-text-row-images')}?excel_row=${encodeURIComponent(excelRow)}`, {
                        credentials: isSnapshotPackPage ? "omit" : "same-origin"
                    });
                    if (ir.ok) {
                        const ij = await ir.json();
                        images = ij.images || [];
                    }
                } catch {
                    images = [];
                }
            }

            while (legalDetailsCache.size >= 100) {
                const k = legalDetailsCache.keys().next().value;
                legalDetailsCache.delete(k);
            }
            legalDetailsCache.set(text, {
                fields: data.fields,
                images,
                recipient_email: data.recipient_email || ""
            });
            legalModalCurrentText = text;
            renderLegalModalContent(data.fields, images, false);
            setLegalModalWordEnabled(true);
        }

        document.getElementById("clearFiltersBtn").addEventListener("click", () => {
            closeRecordList();
            lastTileDrillKey = "";
            state.control_category.length = 0;
            state.inherent.length = 0;
            state.residual.length = 0;
            state.status.length = 0;
            state.year.length = 0;
            state.assessment_year.length = 0;
            state.target_annual.length = 0;
            state.target_quarterly.length = 0;
            state.actual_annual.length = 0;
            state.actual_quarterly.length = 0;
            state.department.length = 0;
            state.legislator.length = 0;
            state.compliance_status.length = 0;
            state.system_name.length = 0;
            state.authority.length = 0;
            state.regulation.length = 0;
            state.subsidiary_company.length = 0;
            state.holding_company.length = 0;
            updateSubsidiaryStatusPill();
            syncSubsidiaryListSelection();
            state.legal_text.length = 0;
            activeFieldKey = "";
            closeLegalModal();
            closeAgingModal();
            closeCompliancePlanModal();
            fetchSummary();
        });

        document.getElementById("legalTextDropdownBtn").addEventListener("click", (event) => {
            event.stopPropagation();
            const dropdown = document.getElementById("legalTextDropdown");
            dropdown.classList.toggle("open");
        });

        document.addEventListener("click", (event) => {
            const dropdown = document.getElementById("legalTextDropdown");
            if (!dropdown.contains(event.target)) {
                closeLegalDropdown();
            }
        });

        function compliancePlanSeedTag(seed) {
            const payload = JSON.stringify(seed).replace(/</g, "\\u003c");
            return `<script id="compliance-plan-seed" type="application/json">${payload}<\/script>`;
        }

        function injectCompliancePlanSeed(html, seed) {
            const seedTag = compliancePlanSeedTag(seed);
            const seedRe = /<script[^>]*id=["']compliance-plan-seed["'][^>]*>[\s\S]*?<\/script>/i;
            if (seedRe.test(html)) {
                return html.replace(seedRe, seedTag);
            }
            if (html.includes("</body>")) {
                return html.replace("</body>", `${seedTag}\n</body>`);
            }
            return html + seedTag;
        }

        function serializeCurrentDashboardHtml(seed) {
            let html = "<!DOCTYPE html>\n" + document.documentElement.outerHTML;
            html = html.replace(/"isLive"\s*:\s*true/, '"isLive": false');
            html = html.replace(/"apiBase"\s*:\s*"[^"]*"/, '"apiBase": ""');
            return injectCompliancePlanSeed(html, seed);
        }

        async function downloadInteractiveSnapshot() {
            const seed = {
                sheetName: compliancePlanState.sheetName,
                headers: compliancePlanState.headers,
                rows: compliancePlanState.rows,
                styles: compliancePlanState.styles,
                selectedCell: compliancePlanState.selectedCell
            };
            let html = "";
            if (__arCfg.isLive !== false && __arApiBase) {
                try {
                    const brandQs = buildFilterQueryString({
                        subsidiary_company: state.subsidiary_company,
                        holding_company: state.holding_company
                    });
                    const response = await fetch(`${arApiUrl("/export-dashboard-html")}?${brandQs.toString()}`, {
                        credentials: "same-origin"
                    });
                    if (response.ok) {
                        html = injectCompliancePlanSeed(await response.text(), seed);
                    }
                } catch (_err) {
                    html = "";
                }
            }
            if (!html) {
                html = serializeCurrentDashboardHtml(seed);
            }
            const blob = new Blob([html], { type: "text/html;charset=utf-8" });
            const name = `dashboard-snapshot-${new Date().toISOString().slice(0, 10)}.html`;
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = name;
            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => URL.revokeObjectURL(url), 120000);
        }

        const downloadBtn = document.getElementById("downloadInteractiveHtmlBtn");
        if (downloadBtn) {
            downloadBtn.addEventListener("click", async () => {
                downloadBtn.disabled = true;
                const original = downloadBtn.textContent;
                downloadBtn.textContent = "جارٍ التنزيل…";
                try {
                    await downloadInteractiveSnapshot();
                } finally {
                    downloadBtn.textContent = original;
                    downloadBtn.disabled = false;
                }
            });
        }

        function initUploadedFilePreview() {
            const panel = document.getElementById("filePreviewPanel");
            const headEl = document.getElementById("filePreviewHead");
            const bodyEl = document.getElementById("filePreviewBody");
            const metaEl = document.getElementById("filePreviewMeta");
            const emptyEl = document.getElementById("filePreviewEmpty");
            const clearBtn = document.getElementById("filePreviewClearBtn");
            if (!panel || !headEl || !bodyEl) {
                return;
            }
            const pack = getSnapshotPack();
            const sourceRows = ((pack && pack.rows) || []).filter((row) => row && typeof row === "object");
            if (!sourceRows.length) {
                panel.hidden = true;
                return;
            }
            const preferred = [
                "الشركة التابعة", "الشركة القابضة", "المشرع", "رقم المادة", "اسم النظام", "اللائحة",
                "الهيئة التابعة", "النص النظامي", "حالة الالتزام بالمتطلبات", "مستوى المخاطر الكامنة",
                "تصنيف المخاطر المتبقية", "فئة الضوابط الرقابية", "حالة الخطة التصحيحية", "الإدارة المسؤولة",
                "نتائج التقييم خلال السنة الحالية", "تاريخ خطة الالتزام", "تاريخ التصحيح المستهدف",
                "الخطة التصحيحية", "البنود/المتطلبات غير الملتزم بها", "مالك المهمة / مالك الإجراء",
                "الشخص المسؤول", "رقم المادة"
            ];
            const longText = new Set([
                "النص النظامي", "الخطة التصحيحية", "البنود/المتطلبات غير الملتزم بها",
                "ملاحظات الإدارة", "مخاطر عدم الالتزام"
            ]);
            const isBlank = (v) => {
                if (v === undefined || v === null || v === "") return true;
                const s = String(v).trim();
                return !s || s === "(blank)" || s === "—" || s === "-";
            };
            const counts = {};
            sourceRows.forEach((row) => {
                Object.keys(row).forEach((key) => {
                    if (!isBlank(row[key])) counts[key] = (counts[key] || 0) + 1;
                });
            });
            const columns = [
                ...preferred.filter((key, idx) => preferred.indexOf(key) === idx && counts[key]),
                ...Object.keys(counts).filter((key) => !preferred.includes(key)).sort((a, b) => a.localeCompare(b, "ar"))
            ];
            if (!columns.length) {
                panel.hidden = true;
                return;
            }
            const uniqueFor = (col) => {
                const set = new Map();
                sourceRows.forEach((row) => {
                    const raw = isBlank(row[col]) ? "" : String(row[col]).trim();
                    const key = raw.toLowerCase();
                    if (!set.has(key)) set.set(key, raw);
                });
                return [...set.values()];
            };
            const useSelect = (col) => !longText.has(col) && uniqueFor(col).length <= 40;
            const filters = {};
            let activePreset = "";

            function cellText(row, col) {
                return isBlank(row[col]) ? "" : String(row[col]).trim();
            }

            function riskText(row) {
                return `${cellText(row, "مستوى المخاطر الكامنة")} ${cellText(row, "تصنيف المخاطر المتبقية")}`;
            }

            function yearHay(row) {
                return [
                    cellText(row, "تاريخ خطة الالتزام"),
                    cellText(row, "نتائج التقييم خلال السنة الحالية"),
                    cellText(row, "تاريخ التصحيح السنوي المستهدف"),
                    cellText(row, "تاريخ التصحيح المستهدف")
                ].join(" ");
            }

            function matchesPreset(row) {
                if (!activePreset) return true;
                const risk = riskText(row);
                const year = String(new Date().getFullYear());
                if (activePreset === "critical") return risk.includes("جدا");
                if (activePreset === "high") return (risk.includes("مرتفع") || risk.includes("عالي")) && !risk.includes("جدا");
                if (activePreset === "medium") return risk.includes("متوسط");
                if (activePreset === "this_year") return yearHay(row).includes(year);
                return true;
            }

            function matchesFilters(row) {
                return columns.every((col) => {
                    const spec = filters[col];
                    if (!spec || !spec.value) return true;
                    const cell = cellText(row, col);
                    if (spec.mode === "select") {
                        if (spec.value === "__blank__") return !cell;
                        return cell === spec.value;
                    }
                    return cell.toLowerCase().includes(spec.value.toLowerCase());
                });
            }

            const numbered = sourceRows.map((row, idx) => ({ row, sn: idx + 1 }));

            function filteredRows() {
                return numbered.filter((item) => matchesPreset(item.row) && matchesFilters(item.row));
            }

            function optionLabel(base, n) {
                return `${base} (${toEnglishNumber(n)})`;
            }

            function renderHead() {
                const sn = document.createElement("th");
                sn.className = "is-sn";
                sn.innerHTML = `<span class="file-preview-col-label">م</span>`;
                const cells = columns.map((col) => {
                    const th = document.createElement("th");
                    const label = document.createElement("span");
                    label.className = "file-preview-col-label";
                    label.textContent = col;
                    th.appendChild(label);
                    if (useSelect(col)) {
                        const select = document.createElement("select");
                        select.className = "file-preview-filter";
                        select.dataset.col = col;
                        select.dataset.mode = "select";
                        const uniques = uniqueFor(col).filter(Boolean).sort((a, b) => a.localeCompare(b, "ar"));
                        const all = document.createElement("option");
                        all.value = "";
                        all.textContent = optionLabel("الكل", sourceRows.length);
                        select.appendChild(all);
                        const blank = document.createElement("option");
                        blank.value = "__blank__";
                        blank.textContent = optionLabel("فارغ", sourceRows.filter((r) => !cellText(r, col)).length);
                        select.appendChild(blank);
                        uniques.forEach((val) => {
                            const opt = document.createElement("option");
                            opt.value = val;
                            opt.textContent = optionLabel(val, sourceRows.filter((r) => cellText(r, col) === val).length);
                            select.appendChild(opt);
                        });
                        select.addEventListener("change", () => {
                            filters[col] = { mode: "select", value: select.value };
                            renderBody();
                        });
                        th.appendChild(select);
                    } else {
                        const input = document.createElement("input");
                        input.type = "search";
                        input.className = "file-preview-filter";
                        input.placeholder = "بحث";
                        input.dataset.col = col;
                        input.dataset.mode = "search";
                        input.addEventListener("input", () => {
                            filters[col] = { mode: "search", value: input.value.trim() };
                            renderBody();
                        });
                        th.appendChild(input);
                    }
                    return th;
                });
                const tr = document.createElement("tr");
                tr.appendChild(sn);
                cells.forEach((th) => tr.appendChild(th));
                headEl.innerHTML = "";
                headEl.appendChild(tr);
            }

            function renderBody() {
                const list = filteredRows();
                bodyEl.innerHTML = "";
                list.forEach((item) => {
                    const tr = document.createElement("tr");
                    const sn = document.createElement("td");
                    sn.className = "is-sn";
                    sn.textContent = toEnglishNumber(item.sn);
                    tr.appendChild(sn);
                    columns.forEach((col) => {
                        const td = document.createElement("td");
                        td.textContent = cellText(item.row, col) || "";
                        tr.appendChild(td);
                    });
                    tr.addEventListener("click", () => {
                        const legal = cellText(item.row, "النص النظامي");
                        if (legal) openLegalDetails(legal);
                    });
                    bodyEl.appendChild(tr);
                });
                if (metaEl) {
                    metaEl.textContent = `${toEnglishNumber(list.length)} من ${toEnglishNumber(sourceRows.length)} صف`;
                }
                if (emptyEl) {
                    emptyEl.hidden = list.length > 0;
                }
            }

            panel.querySelectorAll(".file-preview-preset").forEach((btn) => {
                btn.addEventListener("click", () => {
                    const next = btn.dataset.preset || "";
                    activePreset = activePreset === next ? "" : next;
                    panel.querySelectorAll(".file-preview-preset").forEach((el) => {
                        el.classList.toggle("is-active", el.dataset.preset === activePreset);
                    });
                    renderBody();
                });
            });
            if (clearBtn) {
                clearBtn.addEventListener("click", () => {
                    activePreset = "";
                    Object.keys(filters).forEach((key) => delete filters[key]);
                    panel.querySelectorAll(".file-preview-preset").forEach((el) => el.classList.remove("is-active"));
                    headEl.querySelectorAll(".file-preview-filter").forEach((el) => {
                        el.value = "";
                    });
                    renderBody();
                });
            }
            panel.hidden = false;
            renderHead();
            renderBody();
        }

        function isBlankUploadCell(v) {
            if (v === undefined || v === null || v === "") return true;
            const s = String(v).trim();
            return !s || s === "(blank)" || s === "—" || s === "-";
        }

        function loadUploadedFileCatalog() {
            const pack = getSnapshotPack();
            const sourceRows = ((pack && pack.rows) || []).filter((row) => row && typeof row === "object");
            const preferred = [
                "الشركة التابعة", "الشركة القابضة", "المشرع", "رقم المادة", "اسم النظام", "اللائحة",
                "الهيئة التابعة", "النص النظامي", "حالة الالتزام بالمتطلبات", "مستوى المخاطر الكامنة",
                "تصنيف المخاطر المتبقية", "فئة الضوابط الرقابية", "حالة الخطة التصحيحية", "الإدارة المسؤولة",
                "نتائج التقييم خلال السنة الحالية", "تاريخ خطة الالتزام", "تاريخ التصحيح المستهدف",
                "الخطة التصحيحية", "البنود/المتطلبات غير الملتزم بها", "مالك المهمة / مالك الإجراء",
                "الشخص المسؤول"
            ];
            const counts = {};
            sourceRows.forEach((row) => {
                Object.keys(row).forEach((key) => {
                    if (!isBlankUploadCell(row[key])) counts[key] = (counts[key] || 0) + 1;
                });
            });
            const columns = [
                ...preferred.filter((key, idx) => preferred.indexOf(key) === idx && counts[key]),
                ...Object.keys(counts).filter((key) => !preferred.includes(key)).sort((a, b) => a.localeCompare(b, "ar"))
            ];
            return { sourceRows, columns, counts };
        }

        function initFileColumnStudio() {
            const modal = document.getElementById("fileStudioModal");
            const toggle = document.getElementById("fileStudioToggle");
            const closeBtn = document.getElementById("fileStudioClose");
            const excelBtn = document.getElementById("fileStudioExcelBtn");
            const colList = document.getElementById("fileStudioColList");
            const colSearch = document.getElementById("fileStudioColSearch");
            const rowSearch = document.getElementById("fileStudioRowSearch");
            const headEl = document.getElementById("fileStudioHead");
            const bodyEl = document.getElementById("fileStudioBody");
            const emptyEl = document.getElementById("fileStudioEmpty");
            if (!modal || !toggle) {
                return;
            }
            const catalog = loadUploadedFileCatalog();
            const selected = new Set(catalog.columns.slice(0, Math.min(10, catalog.columns.length)));
            let pickerQuery = "";
            let reviewQuery = "";

            function cellText(row, col) {
                return isBlankUploadCell(row[col]) ? "" : String(row[col]).trim();
            }

            function closeFileStudio() {
                modal.style.display = "none";
                toggle.checked = false;
            }

            function openFileStudio() {
                modal.style.display = "flex";
                const hero = document.getElementById("fileStudioHeroMeta");
                if (hero) {
                    hero.textContent = `${toEnglishNumber(catalog.columns.length)} عمود · ${toEnglishNumber(catalog.sourceRows.length)} صف`;
                }
                renderPicker();
                renderReview();
            }

            function selectedColumns() {
                return catalog.columns.filter((col) => selected.has(col));
            }

            function renderPicker() {
                if (!colList) {
                    return;
                }
                const q = pickerQuery.trim().toLowerCase();
                colList.innerHTML = "";
                catalog.columns.forEach((col) => {
                    if (q && !col.toLowerCase().includes(q)) {
                        return;
                    }
                    const on = selected.has(col);
                    const label = document.createElement("label");
                    label.className = `file-studio-col-item${on ? " is-on" : ""}`;
                    const input = document.createElement("input");
                    input.type = "checkbox";
                    input.checked = on;
                    input.addEventListener("change", () => {
                        if (input.checked) {
                            selected.add(col);
                        } else {
                            selected.delete(col);
                        }
                        renderPicker();
                        renderReview();
                    });
                    const copy = document.createElement("span");
                    copy.className = "file-studio-col-copy";
                    copy.innerHTML = `<span class="file-studio-col-name"></span><span class="file-studio-col-count"></span>`;
                    copy.querySelector(".file-studio-col-name").textContent = col;
                    copy.querySelector(".file-studio-col-count").textContent = `${toEnglishNumber(catalog.counts[col] || 0)} قيمة`;
                    label.appendChild(input);
                    label.appendChild(copy);
                    colList.appendChild(label);
                });
                const picked = document.getElementById("fileStudioPickedMeta");
                if (picked) {
                    picked.textContent = `${toEnglishNumber(selected.size)} من ${toEnglishNumber(catalog.columns.length)} عمود محدد`;
                }
            }

            function visibleRows() {
                const cols = selectedColumns();
                const q = reviewQuery.trim().toLowerCase();
                return catalog.sourceRows
                    .map((row, idx) => ({ row, sn: idx + 1 }))
                    .filter((item) => {
                        if (!q) {
                            return true;
                        }
                        return cols.some((col) => cellText(item.row, col).toLowerCase().includes(q));
                    });
            }

            function renderReview() {
                const cols = selectedColumns();
                const rows = visibleRows();
                if (headEl) {
                    headEl.innerHTML = "";
                    const tr = document.createElement("tr");
                    const sn = document.createElement("th");
                    sn.textContent = "م";
                    tr.appendChild(sn);
                    cols.forEach((col) => {
                        const th = document.createElement("th");
                        th.textContent = col;
                        tr.appendChild(th);
                    });
                    headEl.appendChild(tr);
                }
                if (bodyEl) {
                    bodyEl.innerHTML = "";
                    rows.forEach((item) => {
                        const tr = document.createElement("tr");
                        const sn = document.createElement("td");
                        sn.textContent = toEnglishNumber(item.sn);
                        tr.appendChild(sn);
                        cols.forEach((col) => {
                            const td = document.createElement("td");
                            td.textContent = cellText(item.row, col);
                            tr.appendChild(td);
                        });
                        tr.addEventListener("click", () => {
                            const legal = cellText(item.row, "النص النظامي");
                            if (legal) {
                                openLegalDetails(legal);
                            }
                        });
                        bodyEl.appendChild(tr);
                    });
                }
                const reviewMeta = document.getElementById("fileStudioReviewMeta");
                if (reviewMeta) {
                    reviewMeta.textContent = cols.length
                        ? `${toEnglishNumber(rows.length)} صف · ${toEnglishNumber(cols.length)} عمود`
                        : "لا أعمدة محددة";
                }
                if (emptyEl) {
                    emptyEl.hidden = cols.length > 0;
                }
                if (excelBtn) {
                    excelBtn.disabled = !cols.length || !catalog.sourceRows.length;
                }
            }

            function downloadStudioExcel() {
                const cols = selectedColumns();
                if (!cols.length) {
                    return;
                }
                const rows = visibleRows();
                const header = cols;
                const aoa = [header, ...rows.map((item) => cols.map((col) => cellText(item.row, col)))];
                const stamp = new Date().toISOString().slice(0, 10);
                const name = `سجل-الالتزام-${stamp}.xlsx`;
                if (typeof XLSX !== "undefined" && XLSX.utils && XLSX.writeFile) {
                    const ws = XLSX.utils.aoa_to_sheet(aoa);
                    const wb = XLSX.utils.book_new();
                    XLSX.utils.book_append_sheet(wb, ws, "البيانات");
                    XLSX.writeFile(wb, name);
                    return;
                }
                const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
                const csv = aoa.map((line) => line.map(esc).join(",")).join("\n");
                const blob = new Blob(["\ufeff", csv], { type: "text/csv;charset=utf-8" });
                const a = document.createElement("a");
                a.href = URL.createObjectURL(blob);
                a.download = name.replace(/\.xlsx$/i, ".csv");
                a.click();
                setTimeout(() => URL.revokeObjectURL(a.href), 1500);
            }

            toggle.addEventListener("change", (event) => {
                if (event.target.checked) {
                    openFileStudio();
                } else {
                    closeFileStudio();
                }
            });
            if (closeBtn) {
                closeBtn.addEventListener("click", closeFileStudio);
            }
            modal.addEventListener("click", (event) => {
                if (event.target === modal) {
                    closeFileStudio();
                }
            });
            if (excelBtn) {
                excelBtn.addEventListener("click", downloadStudioExcel);
            }
            document.getElementById("fileStudioSelectAll")?.addEventListener("click", () => {
                catalog.columns.forEach((col) => selected.add(col));
                renderPicker();
                renderReview();
            });
            document.getElementById("fileStudioSelectNone")?.addEventListener("click", () => {
                selected.clear();
                renderPicker();
                renderReview();
            });
            if (colSearch) {
                colSearch.addEventListener("input", () => {
                    pickerQuery = colSearch.value;
                    renderPicker();
                });
            }
            if (rowSearch) {
                rowSearch.addEventListener("input", () => {
                    reviewQuery = rowSearch.value;
                    renderReview();
                });
            }
        }

        function isFileStudioOpen() {
            const modal = document.getElementById("fileStudioModal");
            return !!(modal && modal.style.display === "flex");
        }

        function closeFileStudio() {
            const modal = document.getElementById("fileStudioModal");
            const toggle = document.getElementById("fileStudioToggle");
            if (modal) {
                modal.style.display = "none";
            }
            if (toggle) {
                toggle.checked = false;
            }
        }

        updateBrandLogo();
        initUploadedFilePreview();
        initFileColumnStudio();
        fetchSummary();