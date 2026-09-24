
--Actividades
DECLARE @Hoy          DATE = CAST(GETDATE() AS DATE);
DECLARE @LunesActual  DATE = DATEADD(DAY, DATEDIFF(DAY, 0, @Hoy) / 7 * 7, 0);  -- lunes de la semana en curso
DECLARE @FechaFin     DATE = DATEADD(DAY, -1, @LunesActual);   -- domingo anterior
DECLARE @AnioFiscal   INT = YEAR(@FechaFin);

SELECT distinct
    isnull(v.alias, 'SIN AGENTE')  vendedor_nombre,
	a.fecha,
    COALESCE(c.id, '') AS cliente,	
    c.razonSocial cliente_nombre,   
    a.tipocli   tipoCliente,        
    a.tipo tipo_actividad,			
    a.estatus,						
	a.tieneMinuta
FROM v_Actividades a
left join v_CtesProspectos c on c.id = a.id
left join v_CatAgentes v on v.id_Agente = a.alias
WHERE
    a.estatus in ('Realizada', 'Planificada') 
	and year(a.fecha) = @AnioFiscal