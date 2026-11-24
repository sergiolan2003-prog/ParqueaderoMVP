BEGIN;

CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> 0001_initial

INSERT INTO alembic_version (version_num) VALUES ('0001_initial') RETURNING alembic_version.version_num;

-- Running upgrade 0001_initial -> 0002_modelo_datos

CREATE TABLE sede (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    nombre VARCHAR NOT NULL, 
    zona_horaria VARCHAR NOT NULL, 
    inicio_dia_operativo TIME WITHOUT TIME ZONE NOT NULL, 
    cupos_carro INTEGER NOT NULL, 
    cupos_moto INTEGER NOT NULL, 
    CONSTRAINT pk_sede PRIMARY KEY (id), 
    CONSTRAINT ck_sede_cupos_carro_nonnegative CHECK (cupos_carro >= 0), 
    CONSTRAINT ck_sede_cupos_moto_nonnegative CHECK (cupos_moto >= 0), 
    CONSTRAINT uq_sede_nombre UNIQUE (nombre)
);

CREATE TABLE carril (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    sede_id UUID NOT NULL, 
    sentido VARCHAR NOT NULL, 
    CONSTRAINT pk_carril PRIMARY KEY (id), 
    CONSTRAINT ck_carril_sentido_valid CHECK (sentido IN ('ENTRADA', 'SALIDA')), 
    CONSTRAINT fk_carril_sede_id_sede FOREIGN KEY(sede_id) REFERENCES sede (id)
);

CREATE TABLE vehiculo (
    placa VARCHAR NOT NULL, 
    tipo VARCHAR NOT NULL, 
    CONSTRAINT pk_vehiculo PRIMARY KEY (placa), 
    CONSTRAINT ck_vehiculo_placa_uppercase CHECK (placa = upper(placa)), 
    CONSTRAINT ck_vehiculo_tipo_valid CHECK (tipo IN ('CARRO', 'MOTO'))
);

CREATE TABLE evento_acceso (
    id UUID NOT NULL, 
    placa VARCHAR NOT NULL, 
    carril_id UUID NOT NULL, 
    ocurrido_en TIMESTAMP WITH TIME ZONE NOT NULL, 
    confianza_lpr FLOAT NOT NULL, 
    lectura_manual BOOLEAN DEFAULT false NOT NULL, 
    foto_url VARCHAR, 
    CONSTRAINT pk_evento_acceso PRIMARY KEY (id), 
    CONSTRAINT ck_evento_acceso_confianza_lpr_range CHECK (confianza_lpr >= 0 AND confianza_lpr <= 1), 
    CONSTRAINT fk_evento_acceso_carril_id_carril FOREIGN KEY(carril_id) REFERENCES carril (id), 
    CONSTRAINT fk_evento_acceso_placa_vehiculo FOREIGN KEY(placa) REFERENCES vehiculo (placa)
);

CREATE TABLE tarifa (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    sede_id UUID NOT NULL, 
    tipo_vehiculo VARCHAR NOT NULL, 
    franja VARCHAR NOT NULL, 
    valor NUMERIC(12, 2) NOT NULL, 
    vigente_desde DATE NOT NULL, 
    vigente_hasta DATE, 
    CONSTRAINT pk_tarifa PRIMARY KEY (id), 
    CONSTRAINT ck_tarifa_tipo_vehiculo_valid CHECK (tipo_vehiculo IN ('CARRO', 'MOTO')), 
    CONSTRAINT ck_tarifa_franja_valid CHECK (franja IN ('DIURNA', 'NOCTURNA')), 
    CONSTRAINT ck_tarifa_valor_nonnegative CHECK (valor >= 0), 
    CONSTRAINT ck_tarifa_vigencia_order CHECK (vigente_hasta IS NULL OR vigente_hasta >= vigente_desde), 
    CONSTRAINT fk_tarifa_sede_id_sede FOREIGN KEY(sede_id) REFERENCES sede (id), 
    CONSTRAINT uq_tarifa_sede_tipo_franja_desde UNIQUE (sede_id, tipo_vehiculo, franja, vigente_desde)
);

CREATE TABLE cobro (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    placa VARCHAR NOT NULL, 
    sede_id UUID NOT NULL, 
    dia_operativo DATE NOT NULL, 
    tarifa_id UUID NOT NULL, 
    valor NUMERIC(12, 2) NOT NULL, 
    estado VARCHAR NOT NULL, 
    CONSTRAINT pk_cobro PRIMARY KEY (id), 
    CONSTRAINT ck_cobro_valor_nonnegative CHECK (valor >= 0), 
    CONSTRAINT ck_cobro_estado_valid CHECK (estado IN ('PENDIENTE', 'PAGADO', 'ANULADO', 'VENCIDO')), 
    CONSTRAINT fk_cobro_placa_vehiculo FOREIGN KEY(placa) REFERENCES vehiculo (placa), 
    CONSTRAINT fk_cobro_sede_id_sede FOREIGN KEY(sede_id) REFERENCES sede (id), 
    CONSTRAINT fk_cobro_tarifa_id_tarifa FOREIGN KEY(tarifa_id) REFERENCES tarifa (id), 
    CONSTRAINT uq_cobro_placa_sede_dia UNIQUE (placa, sede_id, dia_operativo)
);

CREATE TABLE pago (
    id UUID DEFAULT gen_random_uuid() NOT NULL, 
    cobro_id UUID NOT NULL, 
    medio VARCHAR NOT NULL, 
    valor NUMERIC(12, 2) NOT NULL, 
    referencia_pasarela VARCHAR NOT NULL, 
    pagado_en TIMESTAMP WITH TIME ZONE NOT NULL, 
    CONSTRAINT pk_pago PRIMARY KEY (id), 
    CONSTRAINT ck_pago_medio_valid CHECK (medio IN ('EFECTIVO', 'TARJETA', 'PSE', 'NEQUI')), 
    CONSTRAINT ck_pago_valor_positive CHECK (valor > 0), 
    CONSTRAINT fk_pago_cobro_id_cobro FOREIGN KEY(cobro_id) REFERENCES cobro (id), 
    CONSTRAINT uq_pago_referencia UNIQUE (referencia_pasarela)
);

UPDATE alembic_version SET version_num='0002_modelo_datos' WHERE alembic_version.version_num = '0001_initial';

-- Running upgrade 0002_modelo_datos -> 0003_usuario_auth

CREATE TABLE usuario (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    username VARCHAR NOT NULL,
    password_hash VARCHAR NOT NULL,
    rol VARCHAR NOT NULL,
    activo BOOLEAN DEFAULT true NOT NULL,
    CONSTRAINT pk_usuario PRIMARY KEY (id),
    CONSTRAINT uq_usuario_username UNIQUE (username),
    CONSTRAINT ck_usuario_ck_usuario_rol_valid CHECK (rol IN ('OPERADOR', 'ADMINISTRADOR'))
);

UPDATE alembic_version SET version_num='0003_usuario_auth' WHERE alembic_version.version_num = '0002_modelo_datos';

-- Running upgrade 0003_usuario_auth -> 0004_pases

CREATE TABLE pase (
    id UUID DEFAULT gen_random_uuid() NOT NULL,
    placa VARCHAR NOT NULL,
    sede_id UUID NOT NULL,
    vigente_desde TIMESTAMP WITH TIME ZONE NOT NULL,
    vigente_hasta TIMESTAMP WITH TIME ZONE NOT NULL,
    CONSTRAINT pk_pase PRIMARY KEY (id),
    CONSTRAINT ck_pase_vigencia_order CHECK (vigente_hasta >= vigente_desde),
    CONSTRAINT fk_pase_placa_vehiculo FOREIGN KEY(placa) REFERENCES vehiculo (placa),
    CONSTRAINT fk_pase_sede_id_sede FOREIGN KEY(sede_id) REFERENCES sede (id)
);

CREATE INDEX ix_pase_placa_sede_vigencia ON pase (placa, sede_id, vigente_desde, vigente_hasta);

UPDATE alembic_version SET version_num='0004_pases' WHERE alembic_version.version_num = '0003_usuario_auth';

COMMIT;

