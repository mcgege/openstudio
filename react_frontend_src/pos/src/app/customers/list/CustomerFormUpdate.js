import React, { Component } from "react"
import { intlShape } from "react-intl"
import PropTypes from "prop-types"
import validator from 'validator'
import { v4 } from "uuid"

import CustomerFormError from "./CustomerFormError"


const CustomerFormUpdate = ({display, customerID, customers, error_data={}, onSubmit=f=>f, onCancel=f=>f}) => 
    <div>
        { !(display) ? null :
        <div className="box box-solid"> 
            <div className="box-header">
                <h3 className="box-title">Edit customer</h3>
                <button onClick={onCancel}
                        className="btn btn-default pull-right">
                    Cancel
                </button>
            </div>
            <div className="box-body">
                <form onSubmit={onSubmit}>
                    <label htmlFor="first_name">First Name</label>
                    <input 
                        id="first_name" 
                        className="form-control"
                        name="first_name" 
                        type="text" 
                        defaultValue={ customers[customerID].first_name }
                    />
                    <CustomerFormError message={ (error_data.first_name) ? error_data.first_name : "" } />
                    <label htmlFor="last_name">Last Name</label>
                    <input 
                        id="last_name" 
                        className="form-control"
                        name="last_name" 
                        type="text" 
                        defaultValue={ customers[customerID].last_name }
                    />
                    <CustomerFormError message={ (error_data.last_name) ? error_data.last_name : "" } />
                    <label htmlFor="email">Email</label>
                    <input 
                        id="email" 
                        className="form-control"
                        name="email" 
                        type="text"
                        defaultValue={ customers[customerID].email} 
                    />
                    <CustomerFormError message={ (error_data.email) ? error_data.email : "" } />
                    <br />
                    <button className="btn btn-primary">Save</button>
                </form>
            </div>
        </div>
        }
    </div>


export default CustomerFormUpdate
