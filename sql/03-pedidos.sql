-- Pedidos
SELECT
    isnull(a.Alias,'SIN AGENTE') vendedor_nombre,
    p.movimiento as op, 
    p.cliente cliente ,
    c.razonsocial cliente_nombre,
    p.descripcionExtra descripcion,
    p.totalLinea importe,
    p.fechaemision fecha_emision,
   --CASE WHEN o.detenido_credito = 1 THEN 1 ELSE 0 END AS detenido_credito
   iif(b.cliente/1>0,1,0) as detenido_credito  --clientes bloqueados
FROM v_PedidosPendientes p
left join v_CtesProspectos c on c.id = p.cliente
left join litocrm.dbo.v_CtesBloqueados b on b.Cliente = p.Cliente
left join v_CatAgentes a on a.id_Agente = p.Agente