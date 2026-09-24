-- Oport abiertas

SELECT DISTINCT 
    ISNULL(a.alias, 'SIN AGENTE') vendedor_nombre,
    op.folio oportunidad_id,
    COALESCE(c.id, '')  AS cliente,  
	c.razonSocial cliente_nombre,
    op.tipoC tipo_cliente,
    op.nomOportunidad descripcion,
    op.valor importe,
    op.descEstatus estatus,
	convert(date, op.fecCreacion) fecha_alta,
    convert(date,op.fecUltimoCambio) fecha_cambio_estatus
FROM v_Oportunidades op
left join v_CtesProspectos c on c.idCandy = op.idCliente
left join v_CatAgentes a on a.id_Agente = op.cveAgente
WHERE op.descEstatus IN ('Autorización','Cotizando', 'Listo p /presupuesto', 'Listo p/cotizar', --'Pre registro', 
'Preprensa Concluida', 'Presupuesto terminado', 'Revisión Tecnica', 'Solicitud de cotizacion', 'Solicitud de OP', 'Solicitud Prepensa') 