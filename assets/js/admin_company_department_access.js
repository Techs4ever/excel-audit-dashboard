/* Limit each company membership's department boxes to that company. */
(function () {
    "use strict";

    function readCatalog() {
        var node = document.querySelector("script.company-department-catalog");
        if (!node) {
            return {};
        }
        try {
            return JSON.parse(node.textContent);
        } catch (error) {
            return {};
        }
    }

    function baseFieldId(row) {
        var select = row.querySelector(
            "select[id$='-department_access'], select[id$='-department_access_from']"
        );
        if (!select) {
            return null;
        }
        var fieldId = select.id;
        if (fieldId.endsWith("_from")) {
            return fieldId.slice(0, -5);
        }
        return fieldId;
    }

    function syncRow(row) {
        if (!row || row.classList.contains("empty-form") || !window.SelectBox) {
            return;
        }
        var fieldId = baseFieldId(row);
        if (!fieldId || fieldId.indexOf("__prefix__") !== -1) {
            return;
        }
        var fromId = fieldId + "_from";
        var toId = fieldId + "_to";
        var fromBox = document.getElementById(fromId);
        var toBox = document.getElementById(toId);
        if (!fromBox || !toBox) {
            return;
        }
        var company = row.querySelector("select[name$='-company']");
        var companyId = company ? String(company.value || "") : "";
        var rows = readCatalog()[companyId] || [];
        var allowed = {};
        rows.forEach(function (item) {
            allowed[String(item.id)] = item.name;
        });
        var chosen = {};
        Array.prototype.forEach.call(toBox.options, function (option) {
            if (allowed[option.value]) {
                chosen[option.value] = true;
            }
        });
        SelectBox.cache[fromId] = [];
        SelectBox.cache[toId] = [];
        rows.forEach(function (item) {
            var value = String(item.id);
            var boxId = chosen[value] ? toId : fromId;
            SelectBox.add_to_cache(boxId, { value: value, text: item.name, displayed: 1 });
        });
        SelectBox.redisplay(fromId);
        SelectBox.redisplay(toId);
        if (window.SelectFilter && typeof SelectFilter.refresh_icons === "function") {
            SelectFilter.refresh_icons(fieldId);
        }
    }

    function boot() {
        var group = document.getElementById("company_memberships-group");
        if (!group) {
            return;
        }
        group.querySelectorAll(".inline-related").forEach(syncRow);
        group.addEventListener("change", function (event) {
            var target = event.target;
            if (!target || !target.matches || !target.matches("select[name$='-company']")) {
                return;
            }
            syncRow(target.closest(".inline-related"));
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
