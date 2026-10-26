"""Permission catalogue and default role templates."""

ALL_PERMISSIONS = [
    "Company.View", "Company.Edit",
    "Branch.View", "Branch.Create", "Branch.Edit", "Branch.Delete",
    "User.View", "User.Create", "User.Edit", "User.Delete",
    "Customer.View", "Customer.Create", "Customer.Edit", "Customer.Delete", "Customer.Assign",
    "Visit.View", "Visit.Create", "Visit.Edit",
    "FollowUp.View", "FollowUp.Create", "FollowUp.Edit", "FollowUp.Complete",
    "Reports.View",
]

# data_scope: "company" = sees all company records; "assigned" = only customers currently assigned to the user.
DEFAULT_ROLES: dict[str, dict] = {
    "Administrator": {"data_scope": "company", "permissions": list(ALL_PERMISSIONS)},
    "Manager": {
        "data_scope": "company",
        "permissions": [
            "Company.View", "Branch.View", "User.View",
            "Customer.View", "Customer.Create", "Customer.Edit", "Customer.Assign",
            "Visit.View", "Visit.Create", "Visit.Edit",
            "FollowUp.View", "FollowUp.Create", "FollowUp.Edit", "FollowUp.Complete",
            "Reports.View",
        ],
    },
    "Salesman": {
        "data_scope": "assigned",
        # No Customer.Create/Edit: salesmen create customers only through the Visit workflow.
        "permissions": [
            "Company.View", "Branch.View",
            "Customer.View",
            "Visit.View", "Visit.Create",
            "FollowUp.View", "FollowUp.Create", "FollowUp.Edit", "FollowUp.Complete",
        ],
    },
}

BUSINESS_TYPES = [
    "EzeeStitch", "Accounts", "Medical", "Tours", "Saloon", "Restaurant", "RealState",
    "Gym", "Mobile POS", "Super Market", "Basic POS Trading", "Basic Sales Trading",
]

# Follow-up status transitions. Completed is final; a cancelled follow-up can be reopened.
FOLLOWUP_TRANSITIONS = {
    "Pending": {"Completed", "Cancelled"},
    "Cancelled": {"Pending"},
    "Completed": set(),
}
