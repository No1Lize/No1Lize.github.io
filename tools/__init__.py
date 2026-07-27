"""数据维护命令。"""

import re

from . import sec_structured_disclosures as _sec_structured_disclosures
from . import us_ir_sec_disclosures as _us_ir_sec_disclosures

# Shared validation contract used by SEC direct and official investor-relations
# mirror transports. Kept here so package and ``python -m`` execution agree.
if not hasattr(_sec_structured_disclosures, "ALLOWED_SEC_DOCUMENT_TYPES"):
    _sec_structured_disclosures.ALLOWED_SEC_DOCUMENT_TYPES = set(
        _sec_structured_disclosures.FORM_TYPES.values()
    )

# Several Q4 investor-relations sites time out when their first page is requested
# with the high-density mobile query. The canonical page responds normally and
# already contains the newest filings. Later pages retain the bounded pagination
# parameters implemented by the crawler.
_original_us_ir_page_url = _us_ir_sec_disclosures.page_url
if not getattr(_original_us_ir_page_url, "_canonical_first_page", False):

    def _canonical_first_page(source, page):
        if int(page) == 0:
            return source.url
        return _original_us_ir_page_url(source, page)

    setattr(_canonical_first_page, "_canonical_first_page", True)
    _us_ir_sec_disclosures.page_url = _canonical_first_page

# IonQ and several Q4 sites render compact labels such as ``Form8-K`` and
# ``Form10-Q``. Insert the semantic separator before applying the shared form
# whitelist so material filings are not mistaken for navigation text.
_original_us_ir_extract_form = _us_ir_sec_disclosures.extract_form
if not getattr(_original_us_ir_extract_form, "_compact_form_compat", False):

    def _compact_form_compat(value):
        normalized = re.sub(
            r"\bFORM(?=(?:10-|8-|20-|6-|S-|F-|424|DEF|PRE|SC|SCHEDULE))",
            "FORM ",
            str(value or ""),
            flags=re.IGNORECASE,
        )
        return _original_us_ir_extract_form(normalized)

    setattr(_compact_form_compat, "_compact_form_compat", True)
    _us_ir_sec_disclosures.extract_form = _compact_form_compat
