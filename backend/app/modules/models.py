"""Import ORM models so Alembic can discover the complete metadata."""

from app.modules.accesos.infrastructure import models as _accesos_models
from app.modules.cobros.infrastructure import models as _cobros_models
from app.modules.pagos.infrastructure import models as _pagos_models
from app.modules.tarifas.infrastructure import models as _tarifas_models
