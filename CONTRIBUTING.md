# Cómo sumar tu proyecto al listado de entregables

Este repositorio reúne los entregables de **TIMMD**. Si aprobaste el taller, tu proyecto puede quedar en la tabla del README para que los cuatrimestres siguientes lo **sigan, lo retomen, lo unifiquen con otros o construyan sobre él**.

La mecánica es simple: se agrega un registro en [`data/entregables.yaml`](data/entregables.yaml) y el README se regenera con un script. Los cambios se integran mediante un **pull request (PR)**.

> 💡 Este documento está pensado para hacer el proceso **con un agente de código** (Claude Code, OpenCode, Cursor, etc.). Los pasos son los mismos a mano o con agente; al final hay un **prompt listo para copiar y pegar**.

## Antes de empezar

Necesitás:

- ✅ El entregable final de la materia **aprobado**.
- ✅ Un repositorio **público** en GitHub con el proyecto (código, datos y documentación).
- ✅ Los datos de todos los integrantes del grupo: nombre completo, mail FIUBA y padrón.
- ✅ [uv](https://docs.astral.sh/uv/) instalado para regenerar el README:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## El flujo, paso a paso

### 1 · Forkeá y cloná el repo

Como alumno no tenés permisos de push en `timmd-9216/timmd-entregables`, así que la forma de trabajar es **fork + branch + PR**:

```bash
# con GitHub CLI (crea el fork y lo clona en un paso)
gh repo fork timmd-9216/timmd-entregables --clone
cd timmd-entregables

# o manualmente: botón "Fork" en github.com/timmd-9216/timmd-entregables y luego
git clone https://github.com/<tu-usuario>/timmd-entregables.git
cd timmd-entregables
git remote add upstream https://github.com/timmd-9216/timmd-entregables.git
```

Si sos miembro de la org y tenés permisos de push, podés clonar directo y saltear el fork.

### 2 · Creá una branch para tu entrega

```bash
git switch -c nuevo-entregable-<titulo-corto>
```

Ejemplo: `git switch -c nuevo-entregable-streamai`.

> ⚠️ No trabajes sobre `main`: cada entrega va en su propia branch.

### 3 · Agregá tu registro en `data/entregables.yaml`

Abrí [`data/entregables.yaml`](data/entregables.yaml) y agregá tu proyecto **al final de la lista `proyectos:`**, copiando el formato de los registros existentes:

```yaml
- repo: https://github.com/<usuario>/<repo>
  titulo: Nombre claro y descriptivo del proyecto
  cuatrimestre: 2026 1C
  descripcion: Qué hace el proyecto, con qué datos o herramientas y qué problema resuelve. 2 o 3 líneas.
  tags:
  - tag-tematico
  - otro-tag
  alumnos:
  - nombre: Nombre Apellido
    mail: nombre@fi.uba.ar
    padron: 100000
```

Convenciones del registro:

| Campo | Regla |
|:------|:------|
| `repo` | URL de GitHub del proyecto, sin `/tree/...` ni rama al final |
| `titulo` | Nombre del proyecto como quieran que aparezca en la tabla |
| `cuatrimestre` | Formato `AAAA S`: `2026 1C`, `2026 2C`, ... |
| `descripcion` | 2-3 líneas: qué hace, con qué datos/herramientas |
| `tags` | Minúsculas y temáticos (`visualizations`, `machine-learning`, `n8n`, `fiuba`, ...). Evitar tecnologías genéricas (`python`, `jupyter notebook`) |
| `alumnos` | **Un solo registro por grupo**: todos los integrantes van en la lista `alumnos` |
| `mail` | Mail FIUBA (`@fi.uba.ar`). Si alguien no completó el formulario: `mail: null` |
| `padron` | Número, sin puntos |

**Importante:** no edites `README.md` a mano — se genera desde el YAML y se pisa en cada regeneración.

### 4 · Regenerá el README

```bash
uv sync                         # instala las dependencias (solo la primera vez)
uv run scripts/build.py readme
```

El script lee el YAML y re-renderiza `README.md`. Si el YAML tiene un error de sintaxis, el script lo marca: corregilo y volvé a correr.

### 5 · Revisá el diff, commiteá y push

```bash
git diff        # debe verse: tu registro en el YAML + tu fila nueva en README.md, nada más
git add data/entregables.yaml README.md
git commit -m "Nuevo entregable: <Título> (2026 1C)"
git push -u origin nuevo-entregable-<titulo-corto>
```

### 6 · Abrí el pull request

Desde GitHub (te sugiere "Compare & pull request" tras el push) o con CLI:

```bash
gh pr create --repo timmd-9216/timmd-entregables \
  --base main \
  --title "Nuevo entregable: <Título> (2026 1C)" \
  --body "$(cat <<'EOF'
### Proyecto
- **Título:**
- **Cuatrimestre:** 2026 1C
- **Repo del proyecto:**
- **Integrantes:** (nombre — padrón)

### Checklist
- [ ] Agregué el registro en `data/entregables.yaml` con los datos de todo el grupo
- [ ] Regeneré `README.md` con `uv run scripts/build.py readme` (el PR incluye el README actualizado)
- [ ] El repo del proyecto es público y accesible
- [ ] No toqué registros de otros proyectos
EOF
)"
```

### 7 · Revisión y merge

- Los docentes revisamos el PR y podemos pedir ajustes (título, descripción, tags). Hacelos en la **misma branch**: el PR se actualiza solo.
- Una vez aprobado, se hace merge y tu proyecto queda visible en la tabla.
- Si tu fork quedó desactualizado para una futura edición, sincronizalo antes: botón **Sync fork** en GitHub, o `git fetch upstream && git rebase upstream/main`.

## Sumarte a un proyecto que ya existe

Otra forma de aportar es **continuar un trabajo anterior** en vez de registrar uno nuevo. Hay dos casos, y se modelan distinto:

### Caso A · Trabajás sobre el repo original del proyecto

El proyecto sigue siendo el mismo: lo que cambia es el equipo. **No** se crea una fila nueva — se agrega tu entrada a la lista `alumnos` de esa fila (hacelo cuando tu aporte esté integrado en el repo original).

El aporte en sí se hace en el **repo del proyecto** (forkeándolo si hace falta, con tus propios PRs hacia él); la edición acá es solo el alta en la fila:

```yaml
- repo: https://github.com/<usuario>/<repo-del-proyecto>
  titulo: ...
  alumnos:
  - nombre: Integrante original
    mail: original@fi.uba.ar
    padron: 100000
  - nombre: Vos            # ← agregás tu entrada acá, sin tocar el resto
    mail: vos@fi.uba.ar
    padron: 200000
```

En la descripción del PR aclará qué aportaste (continuación, fix, nueva feature).

### Caso B · Arrancás un fork o repo nuevo con dirección propia

Si el trabajo diverge (nueva versión, otro enfoque, unificación de varios trabajos), es **otro entregable: fila nueva**. Para que la genealogía no se pierda, el registro lleva un campo `origen` con la URL del repo del que deriva:

```yaml
- repo: https://github.com/<tu-usuario>/<repo-nuevo>
  titulo: Mi Proyecto — continuación de X
  cuatrimestre: 2026 2C
  descripcion: ...
  origen: https://github.com/<usuario>/<repo-original>
  tags:
  - tag-tematico
  alumnos:
  - nombre: Vos
    mail: vos@fi.uba.ar
    padron: 200000
```

En la tabla, la fila nueva se muestra con un `↳ continúa de <repo-original>` debajo del link al repositorio.

### Regla rápida

- **Mismo repo** → misma fila: sumás tu entrada en `alumnos`.
- **Repo nuevo / fork** → fila nueva, con `origen` apuntando al repo del que nace.

### Prompt para tu agente (caso A)

```text
Quiero sumarme como contributor a un proyecto ya listado en timmd-9216/timmd-entregables.

- Proyecto (título o repo, según aparece en la tabla): ...
- Mis datos: Nombre Apellido — mail@fi.uba.ar — padrón
- Qué aporté (1 línea): ...

Hacé lo siguiente:
1. Forkeá y cloná timmd-9216/timmd-entregables a mi cuenta si no lo tengo.
2. Creá una branch nueva: sumo-contributor-<titulo-corto>.
3. En data/entregables.yaml, buscá la fila de ese proyecto y agregá mi entrada a
   la lista `alumnos`, respetando el formato (nombre, mail, padron). No toques
   ningún otro registro ni campo.
4. Corré `uv run scripts/build.py readme` para regenerar el README.
5. Mostrame el diff: solo debe verse mi entrada en esa fila y la fila nueva del
   README conmigo incluido.
6. Commiteá con "Sumo contributor a <proyecto>: <Nombre>" y hacé push.
7. Abrí un pull request hacia timmd-9216/timmd-entregables (base main) con ese
   título y la descripción con lo que aporté.
```

## Atajo: prompt para tu agente de código

Copiá esto en tu agente (completá los `...`):

```text
Quiero sumar mi proyecto de TIMMD al listado de entregables del repo timmd-9216/timmd-entregables.

Datos del proyecto:
- Título: ...
- Cuatrimestre: 2026 1C
- Repositorio del proyecto: https://github.com/...
- Descripción (2-3 líneas): ...
- Tags temáticos (minúsculas): ...
- Integrantes (todos): Nombre Apellido — mail@fi.uba.ar — padrón

Hacé lo siguiente:
1. Si no tengo permisos de push en el repo, forkealo a mi cuenta y cloná mi fork
   (usando gh si está disponible); si no, clonalo directo.
2. Creá una branch nueva: nuevo-entregable-<titulo-corto>.
3. Agregá mi proyecto como nuevo registro al final de la lista `proyectos:` de
   data/entregables.yaml, copiando exactamente el formato de los registros
   existentes. Un solo registro por grupo, con todos los integrantes en `alumnos`.
4. Corré `uv sync` y después `uv run scripts/build.py readme` para regenerar el
   README. No edites README.md a mano: se genera desde el YAML.
5. Mostrame el diff para revisar: solo deben cambiar data/entregables.yaml y README.md.
6. Commiteá con el mensaje "Nuevo entregable: <Título> (2026 1C)" y hacé push.
7. Abrí un pull request hacia timmd-9216/timmd-entregables (base main) con título
   "Nuevo entregable: <Título> (2026 1C)" y descripción con los datos del proyecto
   y el checklist: registro agregado, README regenerado, repo público, registros
   existentes intactos.

Antes de cada paso irreversible (push, PR) confirmame qué vas a hacer.
```

## Preguntas frecuentes

**¿Puedo editar `README.md` directamente?**
No. Se genera desde el YAML con `uv run scripts/build.py readme`; una edición a mano se pisa en la próxima regeneración y el PR no pasa revisión.

**Somos 3 integrantes, ¿hacemos 3 registros?**
No: un registro por proyecto, con los 3 integrantes en la lista `alumnos`.

**Mi repo del proyecto es privado.**
Hacelo público, o conversalo con los docentes para que agreguen el registro por vos.

**¿Puedo sumar un proyecto de un cuatrimestre anterior que no está en la lista?**
¡Sí! Es exactamente el caso pensado para el PR: usá el `cuatrimestre` correspondiente en tu registro.
