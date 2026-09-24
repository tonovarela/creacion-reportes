-- Encabezado

GO
/* =====================================================================*/
--DECLARE @FechaFin     DATE = CAST(DATEADD(DAY, -DATEPART(WEEKDAY, GETDATE()) - 5, CAST(GETDATE() AS DATE)) AS DATE); -- domingo anterior; 
--DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);           -- lunes de esa semana
--DECLARE @FechaInicio  DATE = '07/09/2026'
--DECLARE @FechaFin     DATE = '13/09/2026'

DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso

DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de esa semana
DECLARE @SemanaISO    VARCHAR(8) = CONCAT(YEAR(@FechaFin), '-W', DATEPART(ISO_WEEK, @FechaFin));
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);
DECLARE @MesActual    INT = MONTH(@FechaFin);

/* =====================================================================
   1. encabezado.csv � un rengl�n por vendedor
   ===================================================================== */
SELECT
    v.id_Agente                                         AS id_Agente,
    v.alias                                             AS vendedor_nombre,
    v.mail												AS vendedor_correo,
	@SemanaISO                                          AS semana_iso,
    @FechaInicio                                        AS fecha_inicio,
    @FechaFin                                           AS fecha_fin,

    COALESCE(fs.facturado, 0.00)                        AS facturado_semana,
    COALESCE(fm.facturado, 0.00)                        AS facturado_mes,
    COALESCE(fa.facturado, 0.00)                        AS facturado_ano,

    COALESCE(os.ops_cerradas, 0)                        AS ops_cerradas_semana,
    COALESCE(om.ops_cerradas, 0)                        AS ops_cerradas_mes,
    COALESCE(oa.ops_cerradas, 0)                        AS ops_cerradas_ano,
	
    COALESCE(cs.clientes_facturados, 0)                 AS clientes_facturados_semana,
    COALESCE(cm.clientes_facturados, 0)                 AS clientes_facturados_mes,
    COALESCE(ca.clientes_facturados, 0)                 AS clientes_facturados_ano,
	
    COALESCE(com.devengada_ano, 0.00)                   AS comision_devengada_ano,
    COALESCE(com.pagada_ano, 0.00)                       AS comision_pagada_ano,

	COALESCE(com.devengada_ano - com.pagada_ano, 0.00) AS comision_pendiente_cobranza,
    COALESCE(com.retenida_ano, 0.00)                     AS comision_retenida_ano
	
FROM v_CatAgentes v

---VENTAS--------------------------------------------------------------------
OUTER APPLY (
    SELECT SUM(f.importe) AS facturado
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND f.fechaEmision BETWEEN @FechaInicio AND @FechaFin
) fs
OUTER APPLY (
    SELECT SUM(f.importe) AS facturado
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND YEAR(f.fechaEmision) = @AnioFiscal
      AND MONTH(f.fechaEmision) = @MesActual
) fm
OUTER APPLY (
    SELECT SUM(f.importe) AS facturado
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND YEAR(f.fechaEmision) = @AnioFiscal
) fa
---OPORTUNIDADES--------------------------------------------------------------------
OUTER APPLY (
    SELECT COUNT(DISTINCT oc.idOportunidad) AS ops_cerradas
    FROM v_Oportunidades oc
    WHERE oc.cveAgente = v.id_Agente
      AND oc.fecOrdenConcluida BETWEEN @FechaInicio AND @FechaFin
      AND oc.descEstatus = 'OP Concluida'
) os
OUTER APPLY (
    SELECT COUNT(DISTINCT oc.idOportunidad) AS ops_cerradas
    FROM v_Oportunidades oc
    WHERE oc.cveAgente = v.id_Agente
      AND YEAR(oc.fecOrdenConcluida) = @AnioFiscal AND MONTH(oc.fecOrdenConcluida) = @MesActual
      AND oc.descEstatus = 'OP Concluida'
) om
OUTER APPLY (
    SELECT COUNT(DISTINCT oc.idOportunidad) AS ops_cerradas
    FROM v_Oportunidades oc
    WHERE oc.cveAgente = v.id_Agente
      AND YEAR(oc.fecOrdenConcluida) = @AnioFiscal
      AND oc.descEstatus = 'OP Concluida'
) oa
---CLIENTES FACTURADOS -----------------------------------------------------------
OUTER APPLY (
    SELECT COUNT(DISTINCT f.id_Cliente) AS clientes_facturados
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND f.fechaEmision BETWEEN @FechaInicio AND @FechaFin
) cs
OUTER APPLY (
    SELECT COUNT(DISTINCT f.id_Cliente) AS clientes_facturados
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND YEAR(f.fechaEmision) = @AnioFiscal AND MONTH(f.fechaEmision) = @MesActual
) cm
OUTER APPLY (
    SELECT COUNT(DISTINCT f.id_Cliente) AS clientes_facturados
    FROM v_Ventas f
    WHERE f.id_Agente = v.id_Agente
      AND YEAR(f.fechaEmision) = @AnioFiscal
) ca

---COMISIONES----------------------------------------------------------------------
OUTER APPLY (
SELECT
	sum(c.impComision)							as devengada_ano,
	pagada_ano = (select sum(c1.impPagoCom) from v_ComisionXFact c1 where c1.agente = c.agente and year(c1.fechaEmision) = 2026 and c1.estatusComNombre = 'Pagado' group by c1.agente),
	pendiente_cobranza = (select sum(c1.impComision)   from v_ComisionXFact c1 where c1.agente = c.agente and year(c1.fechaEmision) = 2026 and c1.estatusComNombre <> 'Pagado' group by c1.agente),
	sum(c.impRetencion) 
	as retenida_ano
from v_ComisionXFact c 
    WHERE c.Agente = v.id_Agente
      AND YEAR(c.fechaEmision) = @AnioFiscal
	group by c.agente
) com
GO