/* Show subsidiary checkboxes under a company membership when that company has children. */
(function () {
    "use strict";

    function readCatalog() {
        var node = document.querySelector("script.company-subsidiary-catalog");
        if (!node) {
            return {};
        }
        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            return {};
        }
    }

    function escapeHtml(text) {
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function syncRow(row) {
        if (!row || row.classList.contains("empty-form")) {
            return;
        }
        var box = row.querySelector(".subsidiary-access");
        if (!box) {
            return;
        }
        var list = box.querySelector(".subsidiary-access__list");
        var formRow = box.closest(".form-row");
        if (!list) {
            return;
        }
        var company = row.querySelector(
            "select[name$='-company'], select[name='company']"
        );
        var companyId = company ? String(company.value || "") : "";
        var items = readCatalog()[companyId] || [];
        var fieldName = box.getAttribute("data-field-name") || "";
        if (fieldName.indexOf("__prefix__") !== -1 || !items.length) {
            list.innerHTML = "";
            box.classList.add("is-empty");
            if (formRow) {
                formRow.classList.add("subsidiary-access-hidden");
            }
            return;
        }
        var chosen = {};
        Array.prototype.forEach.call(list.querySelectorAll("input:checked"), function (input) {
            chosen[String(input.value)] = true;
        });
        list.innerHTML = items
            .map(function (item) {
                var value = String(item.id);
                var checked = chosen[value] ? " checked" : "";
                return (
                    "<li><label><input type=\"checkbox\" name=\"" +
                    escapeHtml(fieldName) +
                    "\" value=\"" +
                    escapeHtml(value) +
                    "\"" +
                    checked +
                    "> " +
                    escapeHtml(item.label) +
                    "</label></li>"
                );
            })
            .join("");
        box.classList.remove("is-empty");
        if (formRow) {
            formRow.classList.remove("subsidiary-access-hidden");
        }
    }

    function rowOf(node) {
        return node.closest(".inline-related") || node.closest("form");
    }

    function boot() {
        document.querySelectorAll(".subsidiary-access").forEach(function (box) {
            syncRow(rowOf(box));
        });
        document.addEventListener("change", function (event) {
            var target = event.target;
            if (
                !target ||
                !target.matches ||
                !target.matches("select[name$='-company'], select[name='company']")
            ) {
                return;
            }
            syncRow(rowOf(target));
        });
        document.addEventListener("formset:added", function (event) {
            var row = event.target;
            if (!row || !row.id || row.id.indexOf("company_memberships-") !== 0) {
                return;
            }
            window.setTimeout(function () {
                syncRow(row);
            }, 0);
        });
    }

    window.addEventListener("load", boot);
})();
