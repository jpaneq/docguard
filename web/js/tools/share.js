'use strict';
// Textos listos para enviar: proponer MiDNI en lugar de mandar una copia del DNI, y las
// condiciones que acompañan a una copia protegida. Se copian o se abren en el correo (no se envían solos).

const Share = {
  /** ctx = {who, purpose, ref, signed, ack, password} */
  texts(ctx = {}) {
    const fin = ctx.purpose ? `«${ctx.purpose}»` : 'este trámite';
    const midni = {
      title: 'Proponer MiDNI (trámite en persona)',
      subject: 'Identificación con MiDNI en lugar de copia del DNI',
      body: [
        'Hola:',
        '',
        `Para ${fin} preferiría no enviar una copia de mi DNI. Puedo identificarme en persona con la aplicación oficial MiDNI de la Policía Nacional: les muestro un código QR firmado digitalmente por la Policía, que pueden comprobar al momento escaneándolo, con solo los datos necesarios (normalmente el nivel «DNI simple»: foto, número, nombre y apellidos, fecha de nacimiento, sexo y caducidad).`,
        '',
        'Desde el 2 de abril de 2026, el Real Decreto 255/2025 obliga a las administraciones y a las empresas a aceptar MiDNI para identificarse en los trámites presenciales, con la misma validez que la tarjeta física. Así se comprueba mi identidad sin que tengan que guardar una copia de mi documento, en línea con el principio de minimización de datos del RGPD (art. 5.1.c).',
        '',
        'Si por una obligación legal necesitan conservar una copia (por ejemplo, por la normativa de prevención del blanqueo de capitales), les ruego que me indiquen cuál es y les enviaré una copia protegida y limitada a esa finalidad.',
        '',
        'Un saludo,',
      ].join('\n'),
    };
    const items = [
      `– Solo puede usarla ${ctx.who || 'su destinatario'} para ${fin}.`,
      '– No puede cederse a terceros ni utilizarse para otros fines (RGPD, art. 5.1.b).',
      ctx.until ? `– Solo es válida hasta el ${ctx.until}; después les ruego que la eliminen (RGPD, art. 5.1.e).`
        : '– Les ruego que la eliminen cuando deje de ser necesaria (RGPD, art. 5.1.e).',
    ];
    if (ctx.signed) items.push('– Está firmada digitalmente por mí: cualquier modificación invalida la firma.');
    if (ctx.ref) items.push(`– Lleva la referencia ${ctx.ref}, que identifica esta entrega.`);
    if (ctx.ack) items.push('– Les agradecería que firmen el acuse de recibo que va en el propio PDF (recuadro punteado bajo el documento; por ejemplo, con Adobe Acrobat Reader) y me lo devuelvan.');
    if (ctx.password) items.push('– La contraseña para abrirla se la envío por otro medio.');
    const copia = {
      title: 'Texto para acompañar la copia',
      subject: `Copia de mi DNI para ${ctx.purpose || 'el trámite'}`,
      body: ['Hola:', '', `Les adjunto una copia de mi DNI para ${fin}. La copia está limitada a esa finalidad:`, '',
        ...items, '', 'Un saludo,'].join('\n'),
    };
    return { midni, copia };
  },

  open(kind = 'midni', ctx = {}) {
    const all = this.texts(ctx);
    const sel = h('select', {}, Object.entries(all).map(([k, t]) => h('option', { value: k, selected: k === kind }, t.title)));
    const subj = h('input', { value: all[kind].subject });
    const area = h('textarea', { rows: 14, class: 'share-text' }, all[kind].body);
    sel.onchange = () => { subj.value = all[sel.value].subject; area.value = all[sel.value].body; };
    const info = h('p', { class: 'muted' }, kind === 'midni'
      ? 'MiDNI solo sirve en persona: no permite acreditar tu identidad a distancia por internet. Puedes editar el texto antes de usarlo.'
      : 'Puedes editar el texto antes de usarlo. DocGuard no envía nada: se abre un correo nuevo para que lo revises.');
    modal({
      title: 'Textos para compartir',
      body: h('div', { class: 'share' }, h('label', {}, 'Texto', sel), h('label', {}, 'Asunto', subj), area, info),
      wide: true,
      actions: [
        { label: 'Copiar', fn: async () => { toast(await copyText(area.value) ? 'Texto copiado.' : 'No se ha podido copiar: selecciónalo y cópialo a mano.', ''); return false; } },
        { label: 'Abrir en el correo', primary: true, fn: async () => {
          await copyText(area.value);
          composeMail(subj.value, area.value);
          toast('Correo nuevo abierto (el texto también está copiado, por si no aparece entero).', 'ok', [], 7000);
        } },
        { label: 'Cerrar' },
      ],
    });
  },
};
