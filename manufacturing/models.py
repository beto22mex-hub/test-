# This file now only contains imports and any shared utilities if needed

from django.db import models
from django.contrib.auth.models import User

# All models have been moved to their respective apps:
# - UserProfile -> operators/models.py
# - AuthorizedPart, SerialNumber -> serials/models.py  
# - Operation, ProcessRecord -> operations/models.py
# - Defect -> defects/models.py
# - ProductionAlert, ProductionMetrics -> analytics/models.py

# This file can be used for shared utilities or kept empty
# if no manufacturing-specific models are needed
