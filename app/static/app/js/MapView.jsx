import React from 'react';
import './css/MapView.scss';
import Map from './components/Map';
import $ from 'jquery';
import PropTypes from 'prop-types';
import { _, interpolate } from './classes/gettext';
import update from 'immutability-helper';

class MapView extends React.Component {
  static defaultProps = {
    mapItems: [],
    selectedMapType: 'auto',
    title: "",
    public: false,
    shareButtons: true
  };

  static propTypes = {
    mapItems: PropTypes.array.isRequired, // list of dictionaries where each dict is a {mapType: 'orthophoto', url: <tiles.json>},
    selectedMapType: PropTypes.oneOf(['auto', 'orthophoto', 'plant', 'dsm', 'dtm', 'polyhealth']),
    title: PropTypes.string,
    public: PropTypes.bool,
    shareButtons: PropTypes.bool
  };

  constructor(props) {
    super(props);

    let selectedMapType = props.selectedMapType;

    // Automatically select type based on available tiles
    // and preference order (below)
    if (props.selectedMapType === "auto") {
      let preferredTypes = ['orthophoto', 'dsm', 'dtm', 'polyhealth'];

      for (let i = 0; i < this.props.mapItems.length; i++) {
        let mapItem = this.props.mapItems[i];
        for (let j = 0; j < preferredTypes.length; j++) {
          if (mapItem.tiles.find(t => t.type === preferredTypes[j])) {
            selectedMapType = preferredTypes[j];
            break;
          }
        }
        if (selectedMapType !== "auto") break;
      }
    }

    if (selectedMapType === "auto") selectedMapType = "orthophoto"; // Hope for the best


    let availableAISelections = ['ai_cattle', 'ai_corn', 'ai_field', 'ai_soy'];

    this.selectableAI = new Set();

    for (let i = 0; i < this.props.mapItems.length; i++) {
      let mapItem = this.props.mapItems[i];
      for (let j = 0; j < availableAISelections.length; j++) {
        if (mapItem.tiles.find(t => t.type === availableAISelections[j])) {
          this.selectableAI.add(availableAISelections[j]);
        }
      }
    }

    this.state = {
      selectedMapType,
      tiles: this.getTilesByMapType(selectedMapType),
      aiSelected: new Set()
    };

    this.getTilesByMapType = this.getTilesByMapType.bind(this);
    this.handleMapTypeButton = this.handleMapTypeButton.bind(this);
    this.handleMapTypeButton = this.handleMapTypeButton.bind(this);
  }

  getTilesByMapType(type) {
    // Go through the list of map items and return 
    // only those that match a particular type (in tile format)
    const tiles = [];

    this.props.mapItems.forEach(mapItem => {
      mapItem.tiles.forEach(tile => {
        if (tile.type === type) tiles.push({
          url: tile.url,
          meta: mapItem.meta,
          type: tile.type
        });
      });
    });

    return tiles;
  }

  handleMapTypeButton(type) {
    return () => {
      this.setState(update(this.state, {
        $merge: {
          selectedMapType: type,
          tiles: this.getTilesByMapType(type)
        }
      }));
    };
  }

  handleAiTypeButton(name) {
    return () => {
      if (this.state.aiSelected.has(name)){
        this.setState(update(this.state, {
          aiSelected: { $remove: [name]}
        }));
      }
      else{
        this.setState(update(this.state, {
          aiSelected: { $add: [name]}
        }));
      }
    }
  }

  render() {
    let mapTypeButtons = [
      {
        label: _("Orthophoto"),
        type: "orthophoto",
        icon: "far fa-image"
      },
      {
        label: _("Plant Health"),
        type: "plant",
        icon: "fa fa-seedling"
      },
      {
        label: _("Surface Model"),
        type: "dsm",
        icon: "fa fa-chart-area"
      },
      {
        label: _("Terrain Model"),
        type: "dtm",
        icon: "fa fa-chart-area"
      },
      {
        label: _("Polynomial Health"),
        type: "polyhealth",
        icon: "fa fa-image"
      }
    ].filter(mapType => this.getTilesByMapType(mapType.type).length > 0);


    // label: what's written on the button
    // type: corresponds to the internal representation of that type.
    // name: the trailing name for the route.
    // icon: the icon.
    let aiTypeButtons = [
      {
        label: _("IA Gado"),
        type: "ai_cattle",
        name: "cattle", //route
        icon: "glyphicon glyphicon-screenshot",
      },
      {
        label: _("IA Talhão"),
        type: "ai_field",
        name: "field", //route
        icon: "glyphicon glyphicon-screenshot",
      },
      {
        label: _("IA Daninha (soja)"),
        type: "ai_soy",
        name: "soy", //route
        icon: "glyphicon glyphicon-screenshot",
      },
      {
        label: _("IA Daninha (milho)"),
        type: "ai_corn",
        name: "corn", //route
        icon: "glyphicon glyphicon-screenshot",
      }
    ].filter(aiType => this.selectableAI.has(aiType['type']));

    // If we have only one button, hide it...
    if (mapTypeButtons.length === 1) mapTypeButtons = [];

    return (
      <div className="map-view">
        <div className="map-header-wrapper">
          <div className="map-type-selector" role="group">
            {mapTypeButtons.map(mapType =>
              <button
                key={mapType.type}
                onClick={this.handleMapTypeButton(mapType.type)}
                className={"btn rounded-corners " + (mapType.type === this.state.selectedMapType ? "selected-button" : "default-button")}><i className={mapType.icon}></i> {mapType.label}</button>
            )}
            {
              aiTypeButtons.map(aiType => 
                <button 
                key={aiType.type}
                onClick={this.handleAiTypeButton(aiType.name)}
                className={"btn rounded-corners AI-btn " + (this.state.aiSelected.has(aiType.name) ? "selected-button" : "default-button")}>
                  <i className={aiType.icon}></i> {aiType.label}
                </button>
            )}
          </div> 

          {this.props.title ?
            <div className="text-wrapper">
              <i className="fa fa-globe"></i>
              <h3 className="force-montserrat-bold">{this.props.title}</h3>
            </div>
            : ""}
        </div>

        <div className="map-container">
          <Map
            tiles={this.state.tiles}
            showBackground={true}
            mapType={this.state.selectedMapType}
            public={this.props.public}
            shareButtons={this.props.shareButtons}
            aiSelected={this.state.aiSelected}
          />
        </div>
      </div>);
  }
}




$(function () {
  $("[data-mapview]").each(function () {
    let props = $(this).data();
    delete (props.mapview);
    window.ReactDOM.render(<MapView {...props} />, $(this).get(0));
  });
  $(".map-container").each(function () {
    $(this).get(0).style.height = 'calc(100% - ' + $(".map-header-wrapper").get(0).offsetHeight.toString() + "px)";
  });
  window.addEventListener("resize", () => {
    $(".map-container").get(0).style.height = 'calc(100% - ' + $(".map-header-wrapper").get(0).offsetHeight.toString() + "px)";
  });
});

export default MapView;
