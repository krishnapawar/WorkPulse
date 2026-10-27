/**
 * ==============================================================================
 * WorkPulse - Google Sheets Sync Integration (Google Apps Script)
 * ==============================================================================
 * 
 * SETUP INSTRUCTIONS (Takes less than 1 minute):
 * 1. Open your Google Sheet in a web browser.
 * 2. Click "Extensions" menu -> "Apps Script".
 * 3. Delete any existing code in Code.gs, paste this entire file, and click "Save" (💾).
 * 4. Click "Deploy" (top right) -> "New deployment".
 * 5. Click the gear icon (⚙️) next to "Select type" and select "Web app".
 * 6. Set:
 *    - Description: "WorkPulse Sync"
 *    - Execute as: "Me (<your email>)"
 *    - Who has access: "Anyone" (Required so WorkPulse desktop/mobile can push updates)
 * 7. Click "Deploy" -> Authorize permissions -> Copy the "Web app URL" (ends in /exec).
 * 8. In WorkPulse, click "📊 Google Sheet" button, paste your Web App URL, and click "Test Connection"!
 * ==============================================================================
 */

function doPost(e) {
  var lock = LockService.getScriptLock();
  // Wait up to 20 seconds for other concurrent executions to finish
  var hasLock = lock.tryLock(20000);
  if (!hasLock) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Server busy, please retry in a moment."
    })).setMimeType(ContentService.MimeType.JSON);
  }

  try {
    if (!e || !e.postData || !e.postData.contents) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "No POST body received."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var data = JSON.parse(e.postData.contents);
    var ss = SpreadsheetApp.getActiveSpreadsheet();

    // --------------------------------------------------------------------------
    // ACTION 1: Ping / Health Check
    // --------------------------------------------------------------------------
    if (data.action === "ping") {
      var sheetNames = ss.getSheets().map(function(s) { return s.getName(); });
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Connected to Google Sheet: '" + ss.getName() + "'",
        sheetTitle: ss.getName(),
        sheets: sheetNames
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // Default Headers matching WorkPulse Excel Schema
    var defaultHeaders = [
      "ID", "Date", "Project / Module", "Task Title", "Work Description",
      "Hours Spent", "Status", "Remarks", "Login Time", "Logout Time",
      "Lunch Break", "Tea Break", "Logged At"
    ];

    // --------------------------------------------------------------------------
    // ACTION 2: Sync Single Month Sheet (Default & Recommended)
    // --------------------------------------------------------------------------
    if (data.action === "sync_month" || data.action === "sync_sheet") {
      var sheetName = data.sheet_name || "Work Logs";
      var targetSheet = ss.getSheetByName(sheetName);
      if (!targetSheet) {
        targetSheet = ss.insertSheet(sheetName);
      }

      var headers = data.headers && data.headers.length ? data.headers : defaultHeaders;
      var rows = data.rows || [];

      // Clear previous content
      targetSheet.clearContents();

      // Write Header Row
      var headerRange = targetSheet.getRange(1, 1, 1, headers.length);
      headerRange.setValues([headers]);
      headerRange.setBackground("#1F4E79");
      headerRange.setFontColor("#FFFFFF");
      headerRange.setFontWeight("bold");
      headerRange.setFontFamily("Segoe UI");
      headerRange.setHorizontalAlignment("center");
      headerRange.setVerticalAlignment("middle");
      targetSheet.setRowHeight(1, 32);

      // Write Data Rows
      if (rows.length > 0) {
        var dataRange = targetSheet.getRange(2, 1, rows.length, headers.length);
        dataRange.setValues(rows);
        dataRange.setFontFamily("Segoe UI");
        dataRange.setVerticalAlignment("middle");

        // Batch Format and Color Rows (Single Remote Call for Blazing Speed)
        var backgrounds = [];
        var fontColors = [];
        for (var i = 0; i < rows.length; i++) {
          var status = (rows[i][6] || "").toString().trim().toLowerCase();
          var rowBg = [];
          var rowFg = [];
          var baseBg = "#FFFFFF";
          var baseFg = "#1E293B";

          if (status.indexOf("weekly off") !== -1) {
            baseBg = "#DBEAFE"; baseFg = "#1E40AF";
          } else if (status.indexOf("holiday") !== -1) {
            baseBg = "#FEF3C7"; baseFg = "#92400E";
          } else if (status.indexOf("leave") !== -1) {
            baseBg = "#FEE2E2"; baseFg = "#991B1B";
          }

          for (var c = 0; c < headers.length; c++) {
            if (c === 6 && status.indexOf("completed") !== -1) {
              rowBg.push("#DCFCE7"); rowFg.push("#166534");
            } else {
              rowBg.push(baseBg); rowFg.push(baseFg);
            }
          }
          backgrounds.push(rowBg);
          fontColors.push(rowFg);
        }
        dataRange.setBackgrounds(backgrounds);
        dataRange.setFontColors(fontColors);
      }

      // Fast Preset Column Widths (Avoids slow autoResizeColumn network roundtrips)
      var colWidths = [120, 100, 160, 220, 260, 95, 120, 180, 100, 100, 130, 130, 150];
      for (var col = 1; col <= Math.min(headers.length, colWidths.length); col++) {
        targetSheet.setColumnWidth(col, colWidths[col - 1]);
      }

      // Bring active month tab to front
      ss.setActiveSheet(targetSheet);

      // Clean up empty default "Sheet1" if present so target tab is immediately visible
      var sheet1 = ss.getSheetByName("Sheet1");
      if (sheet1 && ss.getSheets().length > 1 && sheet1.getLastRow() === 0) {
        try { ss.deleteSheet(sheet1); } catch (e) {}
      }

      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Successfully synchronized " + rows.length + " rows to tab '" + sheetName + "'",
        updatedRows: rows.length,
        sheetTitle: ss.getName(),
        tab: sheetName
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // --------------------------------------------------------------------------
    // ACTION 3: Sync All Months Across Entire Workbook
    // --------------------------------------------------------------------------
    if (data.action === "sync_all") {
      var allSheets = data.sheets || {};
      var headers = data.headers && data.headers.length ? data.headers : defaultHeaders;
      var totalRows = 0;
      var syncedTabs = [];

      for (var sName in allSheets) {
        var sRows = allSheets[sName] || [];
        var curSheet = ss.getSheetByName(sName);
        if (!curSheet) {
          curSheet = ss.insertSheet(sName);
        }

        curSheet.clearContents();
        var hRange = curSheet.getRange(1, 1, 1, headers.length);
        hRange.setValues([headers]);
        hRange.setBackground("#1F4E79").setFontColor("#FFFFFF").setFontWeight("bold").setFontFamily("Segoe UI");

        if (sRows.length > 0) {
          var dRange = curSheet.getRange(2, 1, sRows.length, headers.length);
          dRange.setValues(sRows);
          dRange.setFontFamily("Segoe UI");

          var backgrounds = [];
          var fontColors = [];
          for (var ri = 0; ri < sRows.length; ri++) {
            var st = (sRows[ri][6] || "").toString().toLowerCase();
            var bBg = "#FFFFFF";
            var bFg = "#1E293B";
            if (st.indexOf("weekly off") !== -1) {
              bBg = "#DBEAFE"; bFg = "#1E40AF";
            } else if (st.indexOf("holiday") !== -1) {
              bBg = "#FEF3C7"; bFg = "#92400E";
            } else if (st.indexOf("leave") !== -1) {
              bBg = "#FEE2E2"; bFg = "#991B1B";
            }
            var rowBg = [];
            var rowFg = [];
            for (var c = 0; c < headers.length; c++) {
              if (c === 6 && st.indexOf("completed") !== -1) {
                rowBg.push("#DCFCE7"); rowFg.push("#166534");
              } else {
                rowBg.push(bBg); rowFg.push(bFg);
              }
            }
            backgrounds.push(rowBg);
            fontColors.push(rowFg);
          }
          dRange.setBackgrounds(backgrounds);
          dRange.setFontColors(fontColors);
          totalRows += sRows.length;
        }

        var colWidths = [120, 100, 160, 220, 260, 95, 120, 180, 100, 100, 130, 130, 150];
        for (var c = 1; c <= Math.min(headers.length, colWidths.length); c++) {
          curSheet.setColumnWidth(c, colWidths[c - 1]);
        }
        syncedTabs.push(sName);
      }

      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Successfully synchronized " + syncedTabs.length + " month tabs (" + totalRows + " total records) to Google Sheets.",
        totalSheets: syncedTabs.length,
        totalRows: totalRows,
        tabs: syncedTabs
      })).setMimeType(ContentService.MimeType.JSON);
    }

    // --------------------------------------------------------------------------
    // ACTION 4: Append Single Row
    // --------------------------------------------------------------------------
    if (data.action === "append_row") {
      var appendSheetName = data.sheet_name || "Work Logs";
      var appendSheet = ss.getSheetByName(appendSheetName);
      if (!appendSheet) {
        appendSheet = ss.insertSheet(appendSheetName);
        appendSheet.appendRow(data.headers || defaultHeaders);
      }
      appendSheet.appendRow(data.row);
      return ContentService.createTextOutput(JSON.stringify({
        status: "success",
        message: "Row appended successfully."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: "Unknown action: " + data.action
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  } finally {
    lock.releaseLock();
  }
}

function doGet(e) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  return ContentService.createTextOutput(JSON.stringify({
    status: "online",
    message: "WorkPulse Google Apps Script Web App is active!",
    sheetTitle: ss.getName(),
    sheets: ss.getSheets().map(function(s) { return s.getName(); })
  })).setMimeType(ContentService.MimeType.JSON);
}
