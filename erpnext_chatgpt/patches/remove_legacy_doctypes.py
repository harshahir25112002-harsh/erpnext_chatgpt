import frappe

def execute():
    """
    Cleans up legacy duplicate DocTypes: ChatGPT Settings and ChatGPT Prompt Template.
    Leaves AI Settings and Prompt Template as the sole authoritative DocTypes.
    """
    legacy_doctypes = ["ChatGPT Settings", "ChatGPT Prompt Template"]
    for dt in legacy_doctypes:
        if frappe.db.exists("DocType", dt):
            try:
                frappe.delete_doc("DocType", dt, ignore_permissions=True, force=True)
            except Exception as e:
                frappe.log_error(title=f"Could not delete legacy DocType {dt}", message=str(e))
