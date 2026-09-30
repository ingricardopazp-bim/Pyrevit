# -*- coding: utf-8 -*-
"""
ui_forms.py  —  Clash Resolver
Formulario WPF rediseñado. Compatible con IronPython / PyRevit.
"""

import clr
clr.AddReference('PresentationFramework')
clr.AddReference('PresentationCore')
clr.AddReference('WindowsBase')

from System.Windows import Visibility
from System.Windows.Media import SolidColorBrush, Color


# ─────────────────────────────────────────────
#  RESULTADO DEL FORMULARIO
# ─────────────────────────────────────────────
class FormResult:
    def __init__(self):
        self.accepted      = False
        self.element_type  = 'auto'       # siempre auto
        self.angle_type    = 90
        self.direction     = 'auto'
        self.custom_angle  = 45.0
        self.custom_offset = None
        self.deduccion_codo = None        # C en mm; None → cálculo automático desde tablas ANSI/ASTM


# ─────────────────────────────────────────────
#  XAML
# ─────────────────────────────────────────────
XAML = """
<Window
    xmlns="http://schemas.microsoft.com/winfx/2006/xaml/presentation"
    xmlns:x="http://schemas.microsoft.com/winfx/2006/xaml"
    Title="Clash Resolver"
    Width="460" Height="820"
    WindowStartupLocation="CenterScreen"
    ResizeMode="NoResize"
    Background="#F4F6FB"
    FontFamily="Segoe UI">

    <Window.Resources>

        <!-- Tarjeta de opcion seleccionada -->
        <Style x:Key="CardSelected" TargetType="Border">
            <Setter Property="Background"     Value="White"/>
            <Setter Property="BorderBrush"    Value="#2563EB"/>
            <Setter Property="BorderThickness" Value="2"/>
            <Setter Property="CornerRadius"   Value="10"/>
            <Setter Property="Padding"        Value="12,10"/>
            <Setter Property="Margin"         Value="0,0,8,0"/>
            <Setter Property="Cursor"         Value="Hand"/>
        </Style>

        <!-- Tarjeta normal -->
        <Style x:Key="CardNormal" TargetType="Border">
            <Setter Property="Background"     Value="White"/>
            <Setter Property="BorderBrush"    Value="#D1D5DB"/>
            <Setter Property="BorderThickness" Value="1.5"/>
            <Setter Property="CornerRadius"   Value="10"/>
            <Setter Property="Padding"        Value="12,10"/>
            <Setter Property="Margin"         Value="0,0,8,0"/>
            <Setter Property="Cursor"         Value="Hand"/>
        </Style>

        <!-- Boton direccion -->
        <Style x:Key="BtnDir" TargetType="Button">
            <Setter Property="Background"       Value="White"/>
            <Setter Property="Foreground"       Value="#111827"/>
            <Setter Property="FontSize"         Value="12"/>
            <Setter Property="FontWeight"       Value="SemiBold"/>
            <Setter Property="Width"            Value="55"/>
            <Setter Property="Height"           Value="55"/>
            <Setter Property="Cursor"           Value="Hand"/>
            <Setter Property="BorderThickness"  Value="1.5"/>
            <Setter Property="BorderBrush"      Value="#D1D5DB"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border x:Name="bdr"
                                Background="{TemplateBinding Background}"
                                BorderBrush="{TemplateBinding BorderBrush}"
                                BorderThickness="{TemplateBinding BorderThickness}"
                                CornerRadius="12">
                            <ContentPresenter HorizontalAlignment="Center"
                                              VerticalAlignment="Center"/>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <!-- Boton AUTO verde -->
        <Style x:Key="BtnAuto" TargetType="Button">
            <Setter Property="Background"      Value="#059669"/>
            <Setter Property="Foreground"      Value="White"/>
            <Setter Property="FontSize"        Value="15"/>
            <Setter Property="FontWeight"      Value="Bold"/>
            <Setter Property="Height"          Value="56"/>
            <Setter Property="Cursor"          Value="Hand"/>
            <Setter Property="BorderThickness" Value="0"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}"
                                CornerRadius="12"
                                Padding="20,0">
                            <ContentPresenter HorizontalAlignment="Center"
                                              VerticalAlignment="Center"/>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

        <!-- Boton cancelar -->
        <Style x:Key="BtnCancel" TargetType="Button">
            <Setter Property="Background"      Value="White"/>
            <Setter Property="Foreground"      Value="#374151"/>
            <Setter Property="FontSize"        Value="14"/>
            <Setter Property="FontWeight"      Value="SemiBold"/>
            <Setter Property="Height"          Value="44"/>
            <Setter Property="Cursor"          Value="Hand"/>
            <Setter Property="BorderBrush"     Value="#D1D5DB"/>
            <Setter Property="BorderThickness" Value="1.5"/>
            <Setter Property="Template">
                <Setter.Value>
                    <ControlTemplate TargetType="Button">
                        <Border Background="{TemplateBinding Background}"
                                BorderBrush="{TemplateBinding BorderBrush}"
                                BorderThickness="{TemplateBinding BorderThickness}"
                                CornerRadius="10"
                                Padding="20,0">
                            <ContentPresenter HorizontalAlignment="Center"
                                              VerticalAlignment="Center"/>
                        </Border>
                    </ControlTemplate>
                </Setter.Value>
            </Setter>
        </Style>

    </Window.Resources>

    <ScrollViewer VerticalScrollBarVisibility="Auto" Background="#F4F6FB">
    <StackPanel Margin="20,0,20,20">

        <!-- HEADER -->
        <Border Background="#2563EB" CornerRadius="0,0,16,16"
                Padding="20,18,20,18" Margin="-20,0,-20,20">
            <StackPanel Orientation="Horizontal" VerticalAlignment="Center">
                <!-- Icono cuadrado con check -->
                <Border Background="White" CornerRadius="10"
                        Width="44" Height="44" Margin="0,0,14,0">
                    <TextBlock Text="✓" Foreground="#2563EB"
                               FontSize="22" FontWeight="Bold"
                               HorizontalAlignment="Center"
                               VerticalAlignment="Center"/>
                </Border>
                <StackPanel>
                    <TextBlock Text="CLASH RESOLVER"
                               Foreground="White"
                               FontSize="20" FontWeight="Bold"/>
                    <TextBlock Text="Seleccione la dirección para aplicar el desvío"
                               Foreground="#BFDBFE" FontSize="11" Margin="0,2,0,0"/>
                </StackPanel>
            </StackPanel>
        </Border>

        <!-- SECCION 1: TIPO DE DESVIO -->
        <StackPanel Margin="0,0,0,16">
            <StackPanel Orientation="Horizontal" Margin="0,0,0,10">
                <Border Background="#2563EB" CornerRadius="6"
                        Width="24" Height="24" Margin="0,0,8,0">
                    <TextBlock Text="1" Foreground="White" FontWeight="Bold"
                               FontSize="13" HorizontalAlignment="Center"
                               VerticalAlignment="Center"/>
                </Border>
                <TextBlock Text="TIPO DE DESVIO" FontWeight="Bold"
                           FontSize="13" Foreground="#111827"
                           VerticalAlignment="Center"/>
            </StackPanel>

            <!-- Tarjetas de angulo -->
            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>

                <!-- 90 grados = cuadrado: 2 codos a 90° -->
                <Border x:Name="card90" Grid.Column="0" Style="{StaticResource CardSelected}">
                    <Border.InputBindings>
                        <MouseBinding MouseAction="LeftClick" Command="{x:Null}"/>
                    </Border.InputBindings>
                    <StackPanel HorizontalAlignment="Center">
                        <RadioButton x:Name="rbAngle90" IsChecked="True"
                                     Visibility="Collapsed"/>
                        <TextBlock Text="⌐" FontSize="20" Foreground="#2563EB"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="90°" Foreground="#2563EB"
                                   FontSize="12" FontWeight="Bold"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="Cuadrado"
                                   FontSize="10" Foreground="#6B7280"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Border>

                <!-- 45 grados = diagonal: 4 codos a 45° -->
                <Border x:Name="card45" Grid.Column="1" Style="{StaticResource CardNormal}">
                    <StackPanel HorizontalAlignment="Center">
                        <RadioButton x:Name="rbAngle45" IsChecked="False"
                                     Visibility="Collapsed"/>
                        <TextBlock Text="↗" FontSize="20" Foreground="#6B7280"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="45°" Foreground="#6B7280"
                                   FontSize="12" FontWeight="Bold"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="Diagonal"
                                   FontSize="10" Foreground="#6B7280"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Border>

                <!-- Variable -->
                <Border x:Name="cardVar" Grid.Column="2" Style="{StaticResource CardNormal}"
                        Margin="0">
                    <StackPanel HorizontalAlignment="Center">
                        <RadioButton x:Name="rbAngleVar" IsChecked="False"
                                     Visibility="Collapsed"/>
                        <TextBlock Text="∠" FontSize="20" Foreground="#6B7280"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="VAR" Foreground="#6B7280"
                                   FontSize="12" FontWeight="Bold"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="Variable"
                                   FontSize="10" Foreground="#6B7280"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Border>
            </Grid>

            <!-- Input angulo variable -->
            <Border x:Name="panelAngle" Visibility="Collapsed"
                    Background="White" CornerRadius="8" Padding="12,8"
                    BorderBrush="#D1D5DB" BorderThickness="1" Margin="0,8,0,0">
                <StackPanel Orientation="Horizontal">
                    <TextBlock Text="Ángulo:" Foreground="#374151"
                               VerticalAlignment="Center" Margin="0,0,10,0"/>
                    <TextBox x:Name="txtAngle" Width="60" Text="45"
                             Background="#F9FAFB" Foreground="#111827"
                             BorderBrush="#D1D5DB" Padding="6,4"
                             FontSize="13" VerticalContentAlignment="Center"/>
                    <TextBlock Text=" grados" Foreground="#6B7280"
                               VerticalAlignment="Center" Margin="4,0,0,0"/>
                </StackPanel>
            </Border>
        </StackPanel>

        <!-- SECCION 2: DISTANCIA DE DESVIO -->
        <StackPanel Margin="0,0,0,16">
            <StackPanel Orientation="Horizontal" Margin="0,0,0,10">
                <Border Background="#2563EB" CornerRadius="6"
                        Width="24" Height="24" Margin="0,0,8,0">
                    <TextBlock Text="2" Foreground="White" FontWeight="Bold"
                               FontSize="13" HorizontalAlignment="Center"
                               VerticalAlignment="Center"/>
                </Border>
                <TextBlock Text="DISTANCIA DE DESVIO" FontWeight="Bold"
                           FontSize="13" Foreground="#111827"
                           VerticalAlignment="Center"/>
            </StackPanel>

            <Grid>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>

                <!-- Automatico -->
                <Border x:Name="cardOffAuto" Grid.Column="0"
                        Style="{StaticResource CardSelected}">
                    <StackPanel Orientation="Horizontal">
                        <RadioButton x:Name="rbOffsetAuto" IsChecked="True"
                                     Visibility="Collapsed"/>
                        <Border Background="#DBEAFE" CornerRadius="8"
                                Width="40" Height="40" Margin="0,0,10,0">
                            <TextBlock Text="↔" Foreground="#2563EB" FontSize="18"
                                       HorizontalAlignment="Center"
                                       VerticalAlignment="Center"/>
                        </Border>
                        <StackPanel VerticalAlignment="Center">
                            <TextBlock Text="Automático (recomendado)"
                                       FontSize="11" FontWeight="SemiBold"
                                       Foreground="#111827"/>
                            <TextBlock Text="El sistema calcula la distancia óptima según estándares."
                                       FontSize="10" Foreground="#6B7280"
                                       TextWrapping="Wrap"/>
                        </StackPanel>
                    </StackPanel>
                </Border>

                <!-- Manual -->
                <Border x:Name="cardOffMan" Grid.Column="1"
                        Style="{StaticResource CardNormal}" Margin="0">
                    <StackPanel Orientation="Horizontal">
                        <RadioButton x:Name="rbOffsetManual" IsChecked="False"
                                     Visibility="Collapsed"/>
                        <Border Background="#F3F4F6" CornerRadius="8"
                                Width="40" Height="40" Margin="0,0,10,0">
                            <TextBlock Text="📏" FontSize="18"
                                       HorizontalAlignment="Center"
                                       VerticalAlignment="Center"/>
                        </Border>
                        <StackPanel VerticalAlignment="Center">
                            <TextBlock Text="Manual" FontSize="11" FontWeight="SemiBold"
                                       Foreground="#111827"/>
                            <TextBlock Text="Definir manualmente la distancia de desvío."
                                       FontSize="10" Foreground="#6B7280"
                                       TextWrapping="Wrap"/>
                        </StackPanel>
                    </StackPanel>
                </Border>
            </Grid>

            <!-- Input offset manual -->
            <Border x:Name="panelOffset" Visibility="Collapsed"
                    Background="White" CornerRadius="8" Padding="12,8"
                    BorderBrush="#D1D5DB" BorderThickness="1" Margin="0,8,0,0">
                <StackPanel Orientation="Horizontal">
                    <TextBlock Text="Distancia:" Foreground="#374151"
                               VerticalAlignment="Center" Margin="0,0,10,0"/>
                    <TextBox x:Name="txtOffset" Width="70" Text="0.30"
                             Background="#F9FAFB" Foreground="#111827"
                             BorderBrush="#D1D5DB" Padding="6,4"
                             FontSize="13" VerticalContentAlignment="Center"/>
                    <TextBlock Text=" m" Foreground="#6B7280"
                               VerticalAlignment="Center" Margin="4,0,0,0"/>
                </StackPanel>
            </Border>
        </StackPanel>

        <!-- SECCION 3: APLICAR DESVIO — DIRECCION -->
        <StackPanel Margin="0,0,0,0">
            <StackPanel Orientation="Horizontal" Margin="0,0,0,12">
                <Border Background="#2563EB" CornerRadius="6"
                        Width="24" Height="24" Margin="0,0,8,0">
                    <TextBlock Text="3" Foreground="White" FontWeight="Bold"
                               FontSize="13" HorizontalAlignment="Center"
                               VerticalAlignment="Center"/>
                </Border>
                <TextBlock Text="APLICAR DESVIO  —  Selecciona la dirección"
                           FontWeight="Bold" FontSize="13" Foreground="#111827"
                           VerticalAlignment="Center"/>
            </StackPanel>

            <TextBlock Text="Haz clic en la dirección para aplicar el desvío de inmediato:"
                       Foreground="#6B7280" FontSize="11" Margin="0,0,0,12"/>

            <!-- Boton AUTO -->
            <Button x:Name="btnAuto" Style="{StaticResource BtnAuto}"
                    HorizontalAlignment="Stretch" Margin="0,0,0,16">
                <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                    <TextBlock Text="✦ " FontSize="16" VerticalAlignment="Center"/>
                    <StackPanel>
                        <TextBlock Text="AUTO - Recomendación del addin"
                                   FontSize="14" FontWeight="Bold"/>
                        <TextBlock Text="Aplica automáticamente la mejor dirección sugerida."
                                   FontSize="10" Foreground="#A7F3D0"/>
                    </StackPanel>
                </StackPanel>
            </Button>

            <!-- Cruz de direcciones -->
            <Grid HorizontalAlignment="Center" Width="165" Height="165" Margin="0,0,0,16">
                <Grid.RowDefinitions>
                    <RowDefinition Height="*"/>
                    <RowDefinition Height="*"/>
                    <RowDefinition Height="*"/>
                </Grid.RowDefinitions>
                <Grid.ColumnDefinitions>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                    <ColumnDefinition Width="*"/>
                </Grid.ColumnDefinitions>

                <!-- ARRIBA -->
                <Button x:Name="btnArriba" Grid.Row="0" Grid.Column="1"
                        Style="{StaticResource BtnDir}">
                    <StackPanel HorizontalAlignment="Center">
                        <TextBlock Text="↑" Foreground="#059669" FontSize="14"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="ARRIBA" FontSize="9" FontWeight="SemiBold"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Button>

                <!-- IZQ -->
                <Button x:Name="btnIzquierda" Grid.Row="1" Grid.Column="0"
                        Style="{StaticResource BtnDir}">
                    <StackPanel HorizontalAlignment="Center">
                        <TextBlock Text="←" Foreground="#059669" FontSize="14"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="IZQ" FontSize="9" FontWeight="SemiBold"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Button>

                <!-- Centro decorativo -->
                <Border Grid.Row="1" Grid.Column="1"
                        Background="#F3F4F6" CornerRadius="8" Margin="4">
                    <TextBlock Text="↕↔" Foreground="#9CA3AF" FontSize="11"
                               HorizontalAlignment="Center" VerticalAlignment="Center"
                               TextAlignment="Center"/>
                </Border>

                <!-- DER -->
                <Button x:Name="btnDerecha" Grid.Row="1" Grid.Column="2"
                        Style="{StaticResource BtnDir}">
                    <StackPanel HorizontalAlignment="Center">
                        <TextBlock Text="→" Foreground="#059669" FontSize="14"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="DER" FontSize="9" FontWeight="SemiBold"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Button>

                <!-- ABAJO -->
                <Button x:Name="btnAbajo" Grid.Row="2" Grid.Column="1"
                        Style="{StaticResource BtnDir}">
                    <StackPanel HorizontalAlignment="Center">
                        <TextBlock Text="↓" Foreground="#059669" FontSize="14"
                                   HorizontalAlignment="Center"/>
                        <TextBlock Text="ABAJO" FontSize="9" FontWeight="SemiBold"
                                   HorizontalAlignment="Center"/>
                    </StackPanel>
                </Button>
            </Grid>

            <!-- Cancelar -->
            <Button x:Name="btnCancelar" Style="{StaticResource BtnCancel}"
                    HorizontalAlignment="Stretch">
                <StackPanel Orientation="Horizontal" HorizontalAlignment="Center">
                    <TextBlock Text="✕  Cancelar" FontSize="13" FontWeight="SemiBold"/>
                </StackPanel>
            </Button>

        </StackPanel>

    </StackPanel>
    </ScrollViewer>
</Window>
"""


# ─────────────────────────────────────────────
#  CLASE FORMULARIO
# ─────────────────────────────────────────────
class CaballitoForm(object):

    def __init__(self, analyzer=None):
        self.result   = FormResult()
        self.analyzer = analyzer
        self._win     = None
        self._build_ui()

    def _build_ui(self):
        from System.Windows.Markup import XamlReader
        win = XamlReader.Parse(XAML)
        self._win = win

        # Controles de ángulo
        self._rb_45  = win.FindName('rbAngle45')
        self._rb_90  = win.FindName('rbAngle90')
        self._rb_var = win.FindName('rbAngleVar')
        self._panel_angle = win.FindName('panelAngle')
        self._txt_angle   = win.FindName('txtAngle')

        # Tarjetas de ángulo (para cambiar borde)
        self._card45  = win.FindName('card45')
        self._card90  = win.FindName('card90')
        self._cardVar = win.FindName('cardVar')

        # Controles de offset
        self._rb_off_auto = win.FindName('rbOffsetAuto')
        self._rb_off_man  = win.FindName('rbOffsetManual')
        self._panel_offset = win.FindName('panelOffset')
        self._txt_offset   = win.FindName('txtOffset')

        # Tarjetas de offset
        self._cardOffAuto = win.FindName('cardOffAuto')
        self._cardOffMan  = win.FindName('cardOffMan')

        # Botones de dirección
        self._btn_auto = win.FindName('btnAuto')
        self._btn_arr  = win.FindName('btnArriba')
        self._btn_aba  = win.FindName('btnAbajo')
        self._btn_der  = win.FindName('btnDerecha')
        self._btn_izq  = win.FindName('btnIzquierda')
        self._btn_cancel = win.FindName('btnCancelar')

        # Clicks en tarjetas de ángulo
        self._card45.MouseLeftButtonUp  += lambda s, e: self._sel_angle(45)
        self._card90.MouseLeftButtonUp  += lambda s, e: self._sel_angle(90)
        self._cardVar.MouseLeftButtonUp += lambda s, e: self._sel_angle('variable')

        # Clicks en tarjetas de offset
        self._cardOffAuto.MouseLeftButtonUp += lambda s, e: self._sel_offset(False)
        self._cardOffMan.MouseLeftButtonUp  += lambda s, e: self._sel_offset(True)

        # Botones de dirección — aplican directamente
        self._btn_auto.Click += lambda s, e: self._accept_with_dir('auto')
        self._btn_arr.Click  += lambda s, e: self._accept_with_dir('arriba')
        self._btn_aba.Click  += lambda s, e: self._accept_with_dir('abajo')
        self._btn_der.Click  += lambda s, e: self._accept_with_dir('derecha')
        self._btn_izq.Click  += lambda s, e: self._accept_with_dir('izquierda')
        self._btn_cancel.Click += self._on_cancel

        win.ShowDialog()

    # ── Selección de ángulo ──────────────────────────────────────────
    def _sel_angle(self, angle):
        from System.Windows.Media import SolidColorBrush, Color
        blue   = SolidColorBrush(Color.FromRgb(37, 99, 235))
        gray   = SolidColorBrush(Color.FromRgb(209, 213, 219))
        blue_t = SolidColorBrush(Color.FromRgb(37, 99, 235))
        gray_t = SolidColorBrush(Color.FromRgb(107, 114, 128))

        self._card90.BorderBrush  = blue  if angle == 90        else gray
        self._card90.BorderThickness = __import__('System.Windows', fromlist=['Thickness']).Thickness(2) if angle == 90 else __import__('System.Windows', fromlist=['Thickness']).Thickness(1.5)
        self._card45.BorderBrush  = blue  if angle == 45        else gray
        self._cardVar.BorderBrush = blue  if angle == 'variable' else gray

        self._rb_45.IsChecked  = (angle == 45)
        self._rb_90.IsChecked  = (angle == 90)
        self._rb_var.IsChecked = (angle == 'variable')

        self._panel_angle.Visibility = Visibility.Visible if angle == 'variable' else Visibility.Collapsed

    # ── Selección de offset ──────────────────────────────────────────
    def _sel_offset(self, manual):
        from System.Windows.Media import SolidColorBrush, Color
        blue = SolidColorBrush(Color.FromRgb(37, 99, 235))
        gray = SolidColorBrush(Color.FromRgb(209, 213, 219))

        self._cardOffAuto.BorderBrush = gray if manual else blue
        self._cardOffMan.BorderBrush  = blue if manual else gray

        self._rb_off_auto.IsChecked = not manual
        self._rb_off_man.IsChecked  = manual
        self._panel_offset.Visibility = Visibility.Visible if manual else Visibility.Collapsed

    # ── Aceptar con dirección ────────────────────────────────────────
    def _accept_with_dir(self, direction):
        self.result.element_type = 'auto'

        if self._rb_var.IsChecked:
            self.result.angle_type = 'variable'
            try:
                self.result.custom_angle = float(self._txt_angle.Text)
            except Exception:
                self.result.custom_angle = 45.0
        elif self._rb_45.IsChecked:
            # Botón "45°" en UI → caballito DIAGONAL (4 codos, ángulo 45° real)
            self.result.angle_type = 45
        else:
            # Botón "90°" en UI → caballito CUADRADO (2 codos verticales, ángulo 90° real)
            self.result.angle_type = 90

        if self._rb_off_man.IsChecked:
            try:
                self.result.custom_offset = float(self._txt_offset.Text) * 3.28084
            except Exception:
                self.result.custom_offset = None
        else:
            self.result.custom_offset = None

        self.result.direction = direction
        self.result.accepted  = True
        self._win.Close()

    # ── Cancelar ────────────────────────────────────────────────────
    def _on_cancel(self, s, e):
        self.result.accepted = False
        self._win.Close()


# ─────────────────────────────────────────────
#  FUNCIÓN DE CONVENIENCIA
# ─────────────────────────────────────────────
def show_caballito_form(analyzer=None):
    form = CaballitoForm(analyzer=analyzer)
    return form.result
