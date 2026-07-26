"""数据维护命令。"""

from . import sec_structured_disclosures as _sec_structured_disclosures

# Shared validation contract used by SEC direct and official investor-relations
# mirror transports. Kept here so package and ``python -m`` execution agree.
if not hasattr(_sec_structured_disclosures, "ALLOWED_SEC_DOCUMENT_TYPES"):
    _sec_structured_disclosures.ALLOWED_SEC_DOCUMENT_TYPES = set(
        _sec_structured_disclosures.FORM_TYPES.values()
    )
