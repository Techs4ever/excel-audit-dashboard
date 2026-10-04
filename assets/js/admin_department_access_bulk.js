(function () {
  "use strict";

  function boot() {
    var group = document.getElementById("department_accesses-group");
    var catalogNode = document.getElementById("department-access-catalog");
    var addBtn = document.getElementById("dept-access-add-all");
    var removeBtn = document.getElementById("dept-access-remove-all");
    if (!group || !catalogNode || !addBtn || !removeBtn) return;

    var catalog = [];
    try {
      catalog = JSON.parse(catalogNode.textContent || "[]");
    } catch (err) {
      catalog = [];
    }

    function formRows() {
      return Array.prototype.filter.call(
        group.querySelectorAll("tr.form-row"),
        function (row) {
          return !row.classList.contains("empty-form");
        }
      );
    }

    function departmentSelect(row) {
      return row.querySelector('select[name$="-department"]');
    }

    function departmentId(row) {
      var select = departmentSelect(row);
      return select ? String(select.value || "") : "";
    }

    function deleteBox(row) {
      return row.querySelector('input[name$="-DELETE"]');
    }

    function showRow(row) {
      row.classList.remove("dept-access-removed");
      row.style.display = "";
      var box = deleteBox(row);
      if (box) box.checked = false;
    }

    function setDepartment(row, department) {
      var select = departmentSelect(row);
      if (!select) return;
      var id = String(department.id);
      var exists = Array.prototype.some.call(select.options, function (option) {
        return option.value === id;
      });
      if (!exists) {
        select.add(new Option(department.name, id, true, true));
      }
      select.value = id;
      if (window.django && window.django.jQuery) {
        window.django.jQuery(select).trigger("change");
      } else {
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      showRow(row);
    }

    function addRow() {
      var link = group.querySelector("tr.add-row a");
      if (!link) return null;
      var before = formRows().length;
      link.click();
      var rows = formRows();
      if (rows.length <= before) return null;
      return rows[rows.length - 1];
    }

    function blankRow() {
      var rows = formRows();
      for (var i = 0; i < rows.length; i += 1) {
        var row = rows[i];
        if (row.classList.contains("dept-access-removed")) continue;
        var box = deleteBox(row);
        if (box && box.checked) continue;
        if (!departmentId(row)) return row;
      }
      return null;
    }

    function rowForDepartment(department) {
      var id = String(department.id);
      var rows = formRows();
      for (var i = 0; i < rows.length; i += 1) {
        if (departmentId(rows[i]) === id) return rows[i];
      }
      return null;
    }

    function addAll() {
      catalog.forEach(function (department) {
        var existing = rowForDepartment(department);
        if (existing) {
          showRow(existing);
          return;
        }
        var target = blankRow() || addRow();
        if (target) setDepartment(target, department);
      });
    }

    function removeAll() {
      var guard = 0;
      var link = group.querySelector("tr.form-row:not(.empty-form) a.inline-deletelink");
      while (link && guard < 1000) {
        link.click();
        guard += 1;
        link = group.querySelector("tr.form-row:not(.empty-form) a.inline-deletelink");
      }
      formRows().forEach(function (row) {
        var box = deleteBox(row);
        if (!box) return;
        box.checked = true;
        row.classList.add("dept-access-removed");
        row.style.display = "none";
      });
    }

    addBtn.addEventListener("click", addAll);
    removeBtn.addEventListener("click", removeAll);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      setTimeout(boot, 0);
    });
  } else {
    setTimeout(boot, 0);
  }
})();
