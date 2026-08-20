# Configuración compartida por todos los .qmd.

suppressPackageStartupMessages({
  library(tidyverse)
  library(scales)
})

# Los scripts originales usaban "Times New Roman", que no existe en el runner de
# GitHub Actions. "sans" es un alias que R resuelve a la sans disponible en cada
# plataforma, así que el render no depende de la máquina y además pega con la
# tipografía del sitio.
FAM <- "sans"

# Todo el piloto está circunscrito al corte de la tesis: ESI, SII y Forbes se
# cortan en 2019 aunque las fuentes lleguen más lejos, y los estados financieros
# cubren la década 2009-2019, que es lo que alcanza el XBRL de la CMF.
CORTE <- 2019
DESDE <- 2009
HASTA <- CORTE

recortar <- function(df, col = "anio") df[df[[col]] <= HASTA, , drop = FALSE]

# Paleta heredada del análisis de correspondencias de la tesis. Se reusa en todo
# el sitio para que los gráficos se lean como una serie y no como una colección.
PALETA <- c("#003f88", "#ee4266", "#047146", "#a89175", "#cd0f82",
            "#c8abed", "#908d89", "#f4a259", "#3d5a80", "#7d4f50")

TINTA <- "#23282d"
GRIS <- "#5b646c"

tema_mvp <- function(base_size = 12) {
  theme_minimal(base_size = base_size) +
    theme(
      text = element_text(family = FAM, colour = TINTA),
      legend.position = "bottom",
      legend.key.height = unit(0.8, "lines"),
      panel.grid.minor = element_blank(),
      panel.grid.major = element_line(colour = "#e9ecef", linewidth = 0.4),
      axis.title = element_text(size = rel(0.9), colour = GRIS),
      axis.text = element_text(colour = GRIS),
      plot.title = element_text(face = "bold", size = rel(1.05)),
      plot.subtitle = element_text(colour = GRIS, size = rel(0.9)),
      plot.caption = element_text(colour = GRIS, hjust = 0, size = rel(0.75)),
      plot.title.position = "plot",
      plot.caption.position = "plot",
      plot.margin = margin(6, 10, 6, 6),
      strip.background = element_rect(fill = "#f0f2f4", colour = NA),
      strip.text = element_text(colour = TINTA, face = "bold", size = rel(0.85))
    )
}

theme_set(tema_mvp())

# Que la paleta sea el default y no haya que repetirla en cada gráfico.
options(
  ggplot2.discrete.colour = function(...) scale_colour_manual(..., values = PALETA),
  ggplot2.discrete.fill = function(...) scale_fill_manual(..., values = PALETA)
)

anios <- scale_x_continuous(breaks = breaks_width(2))

fmt_miles <- label_comma(big.mark = ".", decimal.mark = ",")
