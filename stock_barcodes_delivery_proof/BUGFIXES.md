# Changelog - Errores Corregidos

## Versión 17.0.1.0.0 - Diciembre 2024

### Errores Encontrados y Solucionados Durante el Desarrollo

#### Error 1: Directivas OWL en Vistas XML

**Error:**

```
Forbidden owl directive used in arch (t-esc)
```

**Causa:** Uso de directivas OWL (`t-esc`, `t-if`) en vistas XML normales de Odoo. Las
directivas OWL solo pueden usarse dentro de templates kanban/qweb, no en vistas de
formulario estándar.

**Ubicación:** `views/stock_barcodes_read_picking_views.xml:59-61`

**Solución:** Reemplazar las directivas OWL con campos Odoo estándar:

```xml
<!-- ANTES (incorrecto) -->
<span class="badge bg-info">
    <t t-esc="delivery_proof_count"/> photo<t t-if="delivery_proof_count != 1">s</t>
</span>

<!-- DESPUÉS (correcto) -->
<field
    name="delivery_proof_count"
    invisible="delivery_proof_count == 0"
    class="badge bg-info"
    readonly="1"
    nolabel="1"
    string="photos"
/>
```

---

#### Error 2: Uso de Atributo 'string' en XPath

**Error:**

```
View inheritance may not use attribute 'string' as a selector
```

**Causa:** Odoo no permite usar el atributo `string` como selector en expresiones xpath
para herencia de vistas. Solo se pueden usar atributos como `name`, `id`, y nombres de
elementos.

**Ubicación:** `views/stock_barcodes_read_picking_views.xml:46`

**Solución:** Usar el campo hijo (`pending_move_ids`) y navegar al padre con `..`:

```xml
<!-- ANTES (incorrecto) -->
<xpath expr="//group[@string='Pending moves']" position="before">

<!-- DESPUÉS (correcto) -->
<xpath expr="//field[@name='pending_move_ids']/.." position="before">
```

---

#### Error 3: Campo en Modelo Incorrecto (Primera Iteración)

**Error:**

```
Field "show_delivery_proof" does not exist in model "wiz.stock.barcodes.read.todo"
```

**Causa:** El xpath `//div[hasclass('oe_kanban_picking_done')]` estaba encontrando
múltiples elementos en la vista heredada, incluyendo elementos dentro del kanban view de
`wiz.stock.barcodes.read.todo`.

**Ubicación:** `views/stock_barcodes_read_picking_views.xml:46`

**Solución (Intento 1):** Cambiar a xpath más específico usando el grupo "Pending
moves":

```xml
<xpath expr="//group[@string='Pending moves']" position="before">
```

---

#### Error 3: Campo en Modelo Incorrecto (Segunda Iteración)

**Error:**

```
Field "show_delivery_proof" does not exist in model "wiz.stock.barcodes.read.todo"
```

**Causa:** El xpath `//field[@name='picking_state']` también estaba ambiguo, ya que
`picking_state` existe en múltiples lugares de la vista, incluyendo dentro del kanban de
`wiz.stock.barcodes.read.todo`.

**Ubicación:** `views/stock_barcodes_read_picking_views.xml:16`

**Solución Final:** Hacer el xpath aún más específico apuntando al campo `picking_state`
que está junto al botón `action_clean_values` en la barra inferior del formulario:

```xml
<!-- ANTES (ambiguo) -->
<xpath expr="//field[@name='picking_state']" position="after">
    <field name="show_delivery_proof" invisible="1"/>
    ...
</xpath>

<!-- DESPUÉS (específico) -->
<xpath expr="//button[@name='action_clean_values']/../field[@name='picking_state']" position="after">
    <field name="show_delivery_proof" invisible="1"/>
    ...
</xpath>
```

---

### Lecciones Aprendidas

1. **Directivas OWL:**

   - Solo usar `t-esc`, `t-if`, `t-foreach`, etc. dentro de templates kanban/qweb
   - En vistas de formulario estándar, usar campos y atributos Odoo nativos

2. **XPaths en Vistas Heredadas:**

   - Siempre verificar que el xpath apunta exactamente al elemento deseado
   - Evitar xpaths ambiguos que puedan coincidir con múltiples elementos
   - Usar rutas más específicas con múltiples niveles (ej: `//button/../field`)
   - Preferir atributos únicos como `@name` combinados con estructura de padre

3. **Depuración de Vistas:**

   - Leer cuidadosamente el mensaje de error para identificar el modelo afectado
   - Revisar la vista padre para entender la estructura completa
   - Usar `xmllint` para validación de sintaxis XML
   - Usar `grep` para encontrar todas las ocurrencias de un elemento

4. **Contexto de Modelo en Vistas:**
   - Recordar que las vistas pueden contener sub-vistas de diferentes modelos (kanban
     embebidos, one2many, etc.)
   - Los xpaths pueden afectar inadvertidamente campos de modelos relacionados
   - Siempre considerar el contexto del modelo cuando se usan campos

---

### Estado Final

✅ **Todos los errores corregidos** ✅ **Validación XML exitosa** ✅ **Script de
verificación pasado** ✅ **Listo para instalación**

---

### Testing Post-Corrección

Para verificar que los errores no vuelvan a ocurrir:

1. **Test de Instalación:**

   ```bash
   ./odoo-bin -d test_db -i stock_barcodes_delivery_proof --test-enable --stop-after-init
   ```

2. **Test de Vistas:**

   - Abrir el wizard de barcode scanner
   - Verificar que los campos invisibles se cargan correctamente
   - Verificar que el botón "Photo" aparece en deliveries
   - Verificar que la sección de galería se muestra correctamente

3. **Test de Modelo:**
   - Verificar que `show_delivery_proof` pertenece a `wiz.stock.barcodes.read.picking`
   - Verificar que `wiz.stock.barcodes.read.todo` no es afectado por nuestros campos

---

**Última actualización:** Diciembre 2024 **Desarrollador:** Antonio Ruban (Binhex)
