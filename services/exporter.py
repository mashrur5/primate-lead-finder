from openpyxl import Workbook

from config import EXPORT_FILE


HEADERS = [
    "Source",
    "Founder Name",
    "Title",
    "Email",
    "Email Status",
    "Email Source",
    "LinkedIn",
    "GitHub",
    "Company",
    "Website",
    "Batch / Origin",
    "Team Size",
    "Description",
    "Fit Score",
    "Fit Reason",
    "Personalized Email Opener",
]


def export_to_xlsx(leads):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Primate Leads"
    sheet.append(HEADERS)

    for lead in leads:
        sheet.append(
            [
                lead.get("source", ""),
                lead.get("founder_name", ""),
                lead.get("founder_title", ""),
                lead.get("email", ""),
                lead.get("email_status", ""),
                lead.get("email_source", ""),
                lead.get("linkedin", ""),
                lead.get("github", ""),
                lead.get("company_name", ""),
                lead.get("website", ""),
                lead.get("batch", ""),
                lead.get("team_size", ""),
                lead.get("description", ""),
                lead.get("score", ""),
                lead.get("fit_reason", ""),
                lead.get("email_opener", ""),
            ]
        )

    widths = [14, 22, 18, 32, 14, 16, 40, 36, 22, 28, 14, 12, 50, 14, 40, 60]
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[chr(64 + index)].width = width

    workbook.save(EXPORT_FILE)
    return EXPORT_FILE
