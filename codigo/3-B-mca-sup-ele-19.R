
#### SINTAXIS RESULTADOS #####

## Paquetes
pacman::p_load(tidyverse, ggrepel, janitor, ca, summarytools, gt, gtsummary)

# PARTE DE CARGAR MODELO GUARDADO
modelo_sup <- readRDS("datos/ele/mca-ele19-burt-sup.rds")
vars <- readRDS("datos/ele/vars-mca-ele19-burt-sup.rds")

# vars tiene las variables que entran al modelo
cats <- apply(vars, 2, function(x) nlevels(as.factor(x)))

# Arma un data frame
mca_df <- data.frame(modelo_sup$colcoord, Variable = rep(names(cats), cats))

# Reasignar los nombres que quieres para los colores
mca_df$Variable <- recode(mca_df$Variable,
  "ciiu" = "Rama",
  "exporta" = "Comercio exterior",
  "grupo" = "Grupo Económico",
  "patrimonio" = "Patrimonio",
  "sindicato" = "Sindicato",
  "trabajo" = "Tamaño empleo",
  "ventas" = "Tamaño ventas"
)

# Convertir a factor en el orden correcto
mca_df$Variable <- factor(mca_df$Variable,
  levels = c("Rama", "Comercio exterior", "Grupo Económico", "Patrimonio",
             "Sindicato", "Tamaño empleo", "Tamaño ventas"))

# Agregar etiquetas
mca_df$Etiqueta <- modelo_sup$levelnames

# Hacemos el gráfico con ggplot2 
plot_mca <- ggplot(data = mca_df, aes(x = X1, y = X2)) +
  geom_hline(yintercept = 0, colour = "gray70") +
  geom_vline(xintercept = 0, colour = "gray70") +
  geom_text_repel(aes(colour = Variable, label = Etiqueta), size = 4,
                  hjust = 0.5, nudge_y = 0.2, show.legend = FALSE,
                  direction = "both", box.padding = 0.5, max.overlaps = Inf,
                  min.segment.length = 0, fontface = "bold",
                  family = "Times New Roman") +
  scale_color_manual(values=c("#c8abed",
                              "#ee4266","#003f88","#cd0f82",
                              "#908d89", "#a89175",
                              "#047146"),
                     labels=c("Rama", "Comercio exterior", "Grupo Económico", "Patrimonio",
                              "Sindicato", "Tamaño empleo", "Tamaño ventas"))+
  geom_point(aes(x = X1, y = X2, color = Variable), alpha = 0.5, size = 2) +
  theme_linedraw() +
  theme(legend.position = "right") +
  theme(text = element_text(family = "Times New Roman")) +
  labs(x = paste0("Dimensión 1: Organización y gran escala (", signif((modelo_sup$inertia.e[1]*100), 3), "%)"),
       y = paste0("Dimensión 2: Escala meso y micro (", signif((modelo_sup$inertia.e[2]*100), 3), "%)")) #+
  #labs(caption=paste0("Elaboración propia con base en ELE 2019. N: ",nrow(vars), " casos."))

plot_mca
