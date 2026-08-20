# Configuración compartida por todos los .qmd.
#
# FAM: los scripts originales usaban "Times New Roman", que no existe en el
# runner de GitHub Actions. "serif" es un alias que R resuelve a la serif
# disponible en cada plataforma, así que el render no depende de la máquina.

suppressPackageStartupMessages({
  library(tidyverse)
  library(scales)
})

FAM <- "serif"

# Todo el piloto está circunscrito al corte de la tesis: ESI, SII y Forbes se
# cortan en 2019 aunque las fuentes lleguen más lejos, y los estados financieros
# cubren la década 2009-2019, que es lo que alcanza el XBRL de la CMF.
CORTE <- 2019
DESDE <- 2009
HASTA <- CORTE

recortar <- function(df, col = "anio") df[df[[col]] <= HASTA, , drop = FALSE]

tema_mvp <- function(base_size = 12) {
  theme_linedraw(base_size = base_size) +
    theme(
      text = element_text(family = FAM),
      legend.position = "bottom",
      panel.grid.minor = element_blank(),
      plot.title = element_text(face = "bold"),
      plot.caption = element_text(colour = "grey40", hjust = 0)
    )
}

theme_set(tema_mvp())

anios <- scale_x_continuous(breaks = breaks_width(2))

fmt_miles <- label_comma(big.mark = ".", decimal.mark = ",")
