/** @odoo-module **/
import { rpc } from "@web/core/network/rpc";

const sendDatesToBackend = async (dates) => {
    try {
        if (!dates.length) return;
        await rpc("/tennis_club/get_new_slots", { dates });
    } catch (err) {
        console.error("Failed to send dates:", err);
    }
};

const fetchWorkingCenterData = async () => {
    try {
        const result = await rpc("/tennis_club/get_new_slots", { method: "POST" });
        return {
            centerName: result.working_center_id || "Unknown Center",
            courts: result.courts || []
        };
    } catch (err) {
        console.error("Failed to fetch working center:", err);
        return { centerName: "Unknown Center", courts: [] };
    }
};

const updateHeaderText = async () => {
    const header = document.querySelector(".o_calendar_header");
    if (!header) return;

    const { centerName, courts } = await fetchWorkingCenterData();

    let span = header.querySelector(".custom-working-center-span");
    if (!span) {
        span = document.createElement("span");
        span.style.marginLeft = "10px";
        span.classList.add("custom-working-center-span");
        header.appendChild(span);
    }

    const courtsText = courts.join(" | ");
    span.innerHTML = `
        <span style="color:red; font-weight:bold;">${centerName}</span>
        ${courtsText ? `<br><span style="color:black;">${courtsText}</span>` : ""}
    `;
};

const startCalendarObserver = () => {
    const target = document.body;
    if (!target) {
        setTimeout(startCalendarObserver, 100);
        return;
    }

    let lastSentDates = new Set();

    const observer = new MutationObserver(() => {
        const headers = document.querySelectorAll(".fc-col-header-cell[data-date]");
        if (!headers.length) return;

        const currentDates = Array.from(headers)
            .map(h => h.getAttribute("data-date"))
            .filter(Boolean);

        const newDates = currentDates.filter(d => !lastSentDates.has(d));

        if (newDates.length) {
            sendDatesToBackend(newDates);
            newDates.forEach(d => lastSentDates.add(d));
            updateHeaderText();
        }
    });

    observer.observe(target, { childList: true, subtree: true });
};

document.addEventListener("DOMContentLoaded", startCalendarObserver);
