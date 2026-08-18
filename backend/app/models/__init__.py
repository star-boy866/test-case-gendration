# Import all model modules so their tables register on Base.metadata
# before Base.metadata.create_all() runs in main.py.
from app.models import audit  # noqa: F401
from app.models import knowledge_base  # noqa: F401
from app.models import cache  # noqa: F401
from app.models import refinement  # noqa: F401
from app.models import export  # noqa: F401
from app.models import evaluation  # noqa: F401
from app.models import user  # noqa: F401
from app.models import cognos_orm  # noqa: F401
from app.models import job  # noqa: F401
from app.models import outbox  # noqa: F401
from app.models import delivery  # noqa: F401
