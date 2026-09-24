-- Entregas

DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso

DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @FechaInicio  DATE = DATEADD(DAY, -6, @FechaFin);      -- lunes de esa semana

DECLARE @AnioFiscal   INT = YEAR(@FechaFin);


SELECT
	isnull(v.alias, 'SIN AGENTE')  vendedor_nombre,
	CONCAT(YEAR(e.fecIniXEntregar), '-W', DATEPART(ISO_WEEK, e.fecIniXEntregar))  AS semana_iso,
    e.numOrden AS op,
    e.idClienteINT cliente,
    e.cliente cliente_nombre,
    convert(date,e.fecIniXEntregar) fecha_compromiso_original,  
    convert(date,e.fecPriEntrega) fecha_entrega, 
    E.valido cumple  
FROM v_Entregas e
left join v_CtesProspectos c on c.id = e.idClienteINT
left join v_CatAgentes v on v.id_Agente = c.agente
WHERE YEAR(e.fecIniXEntregar) = @AnioFiscal