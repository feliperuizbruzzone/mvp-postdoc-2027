# CLASE — Fuerza de trabajo ocupada según categoría en el empleo (CISE), ESI 2010-2024.
#
# Fuente: microdatos ESI (INE). Los años 2010-2023 vienen ya procesados en
# datos/esi/processedESI.RData (objeto datos_completosFE), calculados con
# doctorado/desarrollo/ESI/functions.R. Este script agrega 2024 desde el CSV de
# microdatos, aplicando exactamente la misma metodología, y emite la serie
# completa a datos/cise.csv.
#
# Metodología (idéntica a analizar_datosFE en functions.R):
#   - Universo: ocup_ref == 1 (persona con trabajo de referencia definido).
#   - CISE: 1 = Empleador, 2 = Cuenta propia, 3:7 = Asalariado, resto = Otro.
#   - Se eliminan los estratos con una sola PSU (impiden estimar varianza).
#   - Diseño: as_survey_design(strata = estrato, weights = fact_cal_esi).
#
# El CSV de ESI 2024 no tiene URL de descarga estable, así que se pasa por
# argumento y este script no cuelga de la actualización automática.
#
# Uso:  Rscript scripts/fuentes/esi_cise.R [ruta/a/esi_2024.csv]

suppressPackageStartupMessages({
  library(dplyr)
  library(readr)
  library(srvyr)
})

# El csv de 2024 va por argumento o por la variable de entorno ESI_2024: no hay
# un default portable. datos/cise.csv ya viene versionado, asi que esto solo
# hace falta para regenerarlo.
ARGS <- commandArgs(trailingOnly = TRUE)
CSV_2024 <- if (length(ARGS) >= 1) ARGS[1] else Sys.getenv("ESI_2024", "datos/esi_2024.csv")

recodificar_cise <- function(v) {
  dplyr::case_when(
    v == 1 ~ "Empleador",
    v == 2 ~ "Cuenta propia",
    v %in% 3:7 ~ "Asalariado",
    TRUE ~ "Otro"
  )
}

# Réplica de analizar_datosFE(), vectorizada y con la columna CISE por nombre.
cise_anual <- function(data, col_cise) {
  d <- data |>
    filter(ocup_ref == 1) |>
    mutate(categoria_ocupacion_recod = recodificar_cise(.data[[col_cise]]))

  unicos <- d |>
    count(estrato) |>
    filter(n == 1) |>
    pull(estrato)

  d |>
    filter(!estrato %in% unicos) |>
    as_survey_design(strata = estrato, weights = fact_cal_esi) |>
    group_by(categoria_ocupacion_recod) |>
    summarise(
      frecuencias = survey_total(),
      proporcion  = survey_mean(vartype = "ci", level = 0.95, na.rm = TRUE),
      n           = unweighted(n())
    )
}

# ---- 2010-2023: ya calculado ----
# El .RData trae también las funciones originales (recodificar_cise entre ellas),
# así que se carga en su propio environment para no pisar las de arriba.
esi_env <- new.env()
load("datos/esi/processedESI.RData", envir = esi_env)
previo <- esi_env$datos_completosFE
names(previo)[1] <- "anio"

serie <- previo |>
  mutate(anio = as.integer(anio)) |>   # venía como character en el .RData
  select(anio, categoria = categoria_ocupacion_recod, frecuencias, proporcion, n)

# ---- 2024: se calcula acá ----
if (file.exists(CSV_2024)) {
  message("Procesando ESI 2024 desde ", CSV_2024)
  esi24 <- read_csv(
    CSV_2024,
    col_select = c(ocup_ref, categoria_ocupacion, estrato, fact_cal_esi),
    show_col_types = FALSE, progress = FALSE
  )
  fila24 <- cise_anual(esi24, "categoria_ocupacion") |>
    mutate(anio = 2024L) |>
    select(anio, categoria = categoria_ocupacion_recod, frecuencias, proporcion, n)
  serie <- bind_rows(serie, fila24)
} else {
  warning("No se encontró ", CSV_2024, ": la serie queda hasta 2023.")
}

serie <- serie |> arrange(anio, categoria)

dir.create("datos", showWarnings = FALSE)
write_csv(serie, "datos/cise.csv")

message(sprintf(
  "datos/cise.csv — %d filas, %d-%d, categorías: %s",
  nrow(serie), min(serie$anio), max(serie$anio),
  paste(sort(unique(serie$categoria)), collapse = ", ")
))

# Chequeo: las proporciones de cada año suman 1.
stopifnot(all(abs(tapply(serie$proporcion, serie$anio, sum) - 1) < 1e-6))
