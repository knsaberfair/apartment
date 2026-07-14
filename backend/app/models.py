"""Domain constants for the apartment management MVP.

The first release stores data in memory, but these constants keep status values
centralized so future database models can reuse the same vocabulary.
"""

PROPERTY_STATUSES = {"occupied", "vacant", "reserved", "maintenance"}
CONTRACT_STATUSES = {"active", "expiring", "pending", "terminated"}
PAYMENT_STATUSES = {"paid", "pending", "overdue", "reconciled"}
WORK_ORDER_STATUSES = {"open", "in_progress", "waiting", "resolved"}
WORK_ORDER_PRIORITIES = {"low", "medium", "high", "urgent"}
